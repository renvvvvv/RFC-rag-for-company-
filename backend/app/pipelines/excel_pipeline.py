import os
from typing import List, Dict, Any, Tuple
from uuid import UUID
import pandas as pd
from app.pipelines.base import BaseIngestPipeline


class ExcelIngestPipeline(BaseIngestPipeline):
    """优化版 Excel Pipeline：先提取文本，再切分 Chunks

    改进点：
    1. 智能检测表头行（跳过空行）
    2. 过滤空行空列
    3. 减少元数据描述 chunks
    4. 分离文本提取和切分逻辑
    """

    @property
    def supported_types(self) -> List[str]:
        return ["excel", "xlsx", "xls", "csv"]

    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        # Step 1: 提取文本
        extracted_text, doc_metadata = self._extract_text(file_path)

        # 2026-07-08: 文本清洗（在切分前执行）
        extracted_text = self._clean_text(extracted_text)

        # Step 2: 切分 Chunks
        chunks = self._chunk_text(extracted_text)

        # 合并元数据
        merged_meta = {**(metadata or {}), **doc_metadata}
        for chunk in chunks:
            chunk["metadata"] = {**chunk.get("metadata", {}), **merged_meta}

        return chunks

    def _extract_text(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Step 1: 把 Excel 转成可读纯文本"""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".csv":
            sheets = {"Sheet1": pd.read_csv(file_path)}
        else:
            sheets = pd.read_excel(file_path, sheet_name=None, header=None)

        all_text_parts = []
        sheet_summaries = []

        for sheet_name, df in sheets.items():
            # 清理 DataFrame
            df = self._clean_dataframe(df)

            if df.empty:
                continue

            # 提取有效内容
            sheet_text = self._extract_sheet_text(sheet_name, df)
            if sheet_text:
                all_text_parts.append(sheet_text)
                sheet_summaries.append(f"工作表'{sheet_name}': {len(df)}行有效数据")

        # 合并所有文本
        full_text = "\n\n".join(all_text_parts)

        metadata = {
            "title": os.path.basename(file_path),
            "author": "",
            "page_count": len(sheets),
            "language": self._detect_language(full_text),
            "sheet_summaries": sheet_summaries,
        }

        return full_text, metadata

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理 DataFrame：去掉空行空列，检测表头"""
        # 1. 去掉全空的行和列
        df = df.dropna(how='all', axis=0)  # 去掉全空行
        df = df.dropna(how='all', axis=1)  # 去掉全空列

        if df.empty:
            return df

        # 2. 检测表头行（第一个包含 >=2 个非空单元格的行）
        header_row_idx = self._detect_header_row(df)

        # 3. 如果表头不在第一行，重新设置列名
        if header_row_idx > 0:
            # 把表头行作为列名
            new_columns = df.iloc[header_row_idx].tolist()
            # 去掉表头行之前的数据（包括表头行）
            df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
            # 设置列名
            df.columns = [str(c) if pd.notna(c) else f"列{i}" for i, c in enumerate(new_columns)]
        else:
            # 使用第一行作为列名
            new_columns = df.iloc[0].tolist()
            df = df.iloc[1:].reset_index(drop=True)
            df.columns = [str(c) if pd.notna(c) else f"列{i}" for i, c in enumerate(new_columns)]

        # 4. 再次去掉空行（可能有些行只有空值）
        df = df.replace(r'^\s*$', pd.NA, regex=True)
        df = df.dropna(how='all', axis=0)

        # 5. 填充剩余空值
        df = df.fillna("")

        return df

    def _detect_header_row(self, df: pd.DataFrame) -> int:
        """检测表头行：第一个包含 >=2 个非空单元格的行"""
        for i, row in df.iterrows():
            non_empty_count = sum(1 for cell in row if pd.notna(cell) and str(cell).strip())
            if non_empty_count >= 2:
                return i
        return 0  # 默认第一行

    def _extract_sheet_text(self, sheet_name: str, df: pd.DataFrame) -> str:
        """提取单个工作表的文本内容"""
        parts = []

        # 添加工作表标题
        parts.append(f"【{sheet_name}】")

        # 添加列名（如果有意义的话）
        columns = df.columns.tolist()
        if not all(str(c).startswith("列") for c in columns):
            # 列名不是自动生成的，说明有表头
            parts.append(f"列: {', '.join(str(c) for c in columns)}")

        # 逐行提取内容
        for idx, row in df.iterrows():
            row_parts = []
            for col in df.columns:
                value = str(row[col]).strip()
                if value and value != "NaT":
                    # 只输出有值的列
                    row_parts.append(f"{col}: {value}")

            if row_parts:
                parts.append("; ".join(row_parts))

        return "\n".join(parts)

    def _chunk_text(
        self,
        text: str,
        target_size: int = 600,
        min_size: int = 200,
        max_size: int = 1000,
        overlap: int = 100,
    ) -> List[Dict[str, Any]]:
        """Step 2: 切分文本为 Chunks（复用 document_pipeline 的逻辑）"""
        chunks = []
        if not text or not text.strip():
            return chunks

        # 1. 先按段落切分（遇到空行就切）
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        # 如果段落数量太少，尝试按单个换行符切分
        if len(paragraphs) < 3:
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        # 2. 合并小段落
        merged = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) <= target_size:
                current += "\n\n" + para if current else para
            else:
                if current:
                    merged.append(current)
                current = para
        if current:
            merged.append(current)

        # 3. 拆分大段落
        for chunk in merged:
            if len(chunk) > max_size:
                # 按句子切分
                sentences = self._split_by_sentence(chunk)
                sub_chunks = self._merge_sentences(sentences, target_size)
                for sub_chunk in sub_chunks:
                    chunks.append(sub_chunk)
            else:
                chunks.append(chunk)

        # 4. 合并小 chunks
        chunks = self._merge_small_chunks(chunks, min_size)

        # 5. 添加 overlap
        chunks_with_overlap = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev = chunks[i-1]
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                chunk = overlap_text + "\n\n" + chunk
            chunks_with_overlap.append(chunk)

        # 6. 格式化输出
        result = []
        for i, chunk_text in enumerate(chunks_with_overlap):
            result.append({
                "content": chunk_text,
                "modality": "table",
                "chunk_index": i,
                "position_info": {"chunk_index": i, "type": "excel"},
                "metadata": {},
            })

        return result

    def _split_by_sentence(self, text: str) -> List[str]:
        """按句子切分"""
        import re
        pattern = r'(?<=[。！？.!?;；])\s*'
        return [s.strip() for s in re.split(pattern, text) if s.strip()]

    def _merge_sentences(self, sentences: List[str], target_size: int) -> List[str]:
        """合并句子到合适的 chunk 大小"""
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= target_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _merge_small_chunks(self, chunks: List[str], min_size: int) -> List[str]:
        """合并过小的 chunks"""
        if not chunks:
            return chunks

        merged = []
        current = chunks[0]

        for chunk in chunks[1:]:
            if len(current) < min_size:
                current += "\n\n" + chunk
            else:
                merged.append(current)
                current = chunk

        merged.append(current)

        # 再次检查
        final_merged = []
        for chunk in merged:
            if len(chunk) < min_size and final_merged:
                final_merged[-1] += "\n\n" + chunk
            else:
                final_merged.append(chunk)

        return final_merged

    def _detect_language(self, text: str) -> str:
        """简单语言检测"""
        if not text:
            return ""
        # 统计中文字符比例
        chinese_count = sum(1 for c in text if '一' <= c <= '鿿')
        total_count = len(text)
        if total_count == 0:
            return ""
        return "zh" if chinese_count / total_count > 0.1 else "en"
