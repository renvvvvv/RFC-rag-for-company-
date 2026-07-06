import logging
import os
import re
from typing import List, Dict, Any, Tuple
from uuid import UUID
from app.pipelines.base import BaseIngestPipeline

logger = logging.getLogger(__name__)


class DocumentIngestPipeline(BaseIngestPipeline):
    """处理 doc/docx/pdf/pptx/txt/markdown/html/json 文档。

    支持：
    - PDF 文本抽取，失败页面使用 OCR 回退
    - 表格抽取并包裹 [TABLE]...[/TABLE] 标记
    - 元数据提取（title/author/page_count/language）
    - 外部依赖缺失时优雅降级并返回 TODO 占位提示
    """

    @property
    def supported_types(self) -> List[str]:
        return [
            "document", "pdf", "txt", "markdown", "md",
            "html", "htm", "pptx", "ppt", "json",
            "docx", "doc",
        ]

    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        ext = os.path.splitext(file_path)[1].lower()

        extracted_text = ""
        doc_metadata: Dict[str, Any] = {}

        if ext in [".docx", ".doc"]:
            extracted_text, doc_metadata = self._extract_docx(file_path)
        elif ext == ".pdf":
            extracted_text, doc_metadata = self._extract_pdf(file_path)
        elif ext in [".pptx", ".ppt"]:
            extracted_text, doc_metadata = self._extract_pptx(file_path)
        elif ext in [".txt", ".md", ".markdown"]:
            extracted_text, doc_metadata = self._extract_txt(file_path)
        elif ext in [".html", ".htm"]:
            extracted_text, doc_metadata = self._extract_html(file_path)
        elif ext == ".json":
            extracted_text, doc_metadata = self._extract_json(file_path)
        else:
            extracted_text = ""

        merged_meta = {**metadata, **doc_metadata}
        chunks = self._chunk_text(extracted_text)
        for chunk in chunks:
            chunk["metadata"] = {**chunk.get("metadata", {}), **merged_meta}
        return chunks

    def _extract_docx(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        try:
            import docx
            doc = docx.Document(file_path)
            parts = []

            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text)

            # 表格抽取：仅做标记，不参与布局顺序还原
            for table in doc.tables:
                parts.append("[TABLE]")
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells)
                    parts.append(row_text)
                parts.append("[/TABLE]")

            text = "\n".join(parts)
            core_props = doc.core_properties
            metadata = {
                "title": core_props.title or "",
                "author": core_props.author or "",
                "page_count": None,  # DOCX 无固定页数
                "language": self._detect_language(text),
            }
            return text, metadata
        except Exception as e:
            return f"[解析失败: {str(e)}]", {}

    def _extract_pdf(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        try:
            import pdfplumber
            texts = []
            metadata: Dict[str, Any] = {}

            with pdfplumber.open(file_path) as pdf:
                if pdf.metadata:
                    metadata = {
                        "title": pdf.metadata.get("Title", ""),
                        "author": pdf.metadata.get("Author", ""),
                    }
                metadata["page_count"] = len(pdf.pages)

                for page_idx, page in enumerate(pdf.pages):
                    text = page.extract_text()

                    if not text or not text.strip():
                        # OCR 回退：扫描型 PDF 页面
                        ocr_text = self._ocr_pdf_page(file_path, page_idx)
                        if ocr_text and ocr_text != "[OCR disabled]":
                            texts.append(f"[OCR_PAGE {page_idx + 1}]\n{ocr_text}\n[/OCR_PAGE]")
                    else:
                        # 表格标记
                        page_tables = page.extract_tables() or []
                        for table in page_tables:
                            if table:
                                texts.append("[TABLE]")
                                for row in table:
                                    texts.append(
                                        " | ".join(
                                            str(cell) if cell is not None else ""
                                            for cell in row
                                        )
                                    )
                                texts.append("[/TABLE]")
                        texts.append(text)

            metadata["language"] = self._detect_language("\n".join(texts))
            return "\n".join(texts), metadata
        except Exception as e:
            return f"[解析失败: {str(e)}]", {}

    def _ocr_pdf_page(self, file_path: str, page_number: int) -> str:
        """使用 pdf2image + pytesseract 对单页 PDF 做 OCR；开关关闭或依赖缺失时返回占位提示。"""
        if os.getenv("OCR_ENABLED", "true").lower() != "true":
            logger.warning(
                "PDF OCR fallback is disabled by OCR_ENABLED=false for %s page %d",
                file_path,
                page_number + 1,
            )
            return "[OCR disabled]"

        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(
                file_path,
                first_page=page_number + 1,
                last_page=page_number + 1,
            )
            if images:
                return pytesseract.image_to_string(images[0], lang="chi_sim+eng")
            return ""
        except Exception as exc:
            logger.warning(
                "PDF OCR dependencies missing or failed for %s page %d: %s",
                file_path,
                page_number + 1,
                exc,
            )
            return "[OCR disabled]"

    def _extract_pptx(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            texts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text.strip())

            core_props = prs.core_properties
            metadata = {
                "title": core_props.title or "",
                "author": core_props.author or "",
                "page_count": len(prs.slides),
                "language": self._detect_language("\n".join(texts)),
            }
            return "\n".join(texts), metadata
        except Exception as e:
            return f"[解析失败: {str(e)}]", {}

    def _extract_txt(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        metadata = {
            "title": "",
            "author": "",
            "page_count": 1,
            "language": self._detect_language(text),
        }
        return text, metadata

    def _extract_html(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            metadata = {
                "title": title,
                "author": "",
                "page_count": 1,
                "language": self._detect_language(text),
            }
            return text, metadata
        except Exception as e:
            return f"[解析失败: {str(e)}]", {}

    def _extract_json(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        try:
            import json
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            metadata = {
                "title": "",
                "author": "",
                "page_count": 1,
                "language": self._detect_language(text),
            }
            return text, metadata
        except Exception as e:
            return f"[解析失败: {str(e)}]", {}

    def _detect_language(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        try:
            from langdetect import detect
            return detect(text[:2000])
        except Exception:
            # TODO: 安装 langdetect 后启用语言检测。
            return ""

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 100,
    ) -> List[Dict[str, Any]]:
        chunks = []
        if not text:
            return chunks

        start = 0
        chunk_index = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            chunks.append({
                "content": chunk_text,
                "modality": "text",
                "chunk_index": chunk_index,
                "position_info": {"paragraph_range": [start, end]},
                "metadata": {},
            })

            start += chunk_size - overlap
            chunk_index += 1

        return chunks
