import os
from typing import List, Dict, Any
from uuid import UUID
import pandas as pd
from app.pipelines.base import BaseIngestPipeline

class ExcelIngestPipeline(BaseIngestPipeline):
    """处理 xls/xlsx/csv 表格"""
    
    @property
    def supported_types(self) -> List[str]:
        return ["excel"]
    
    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".csv":
            sheets = {"Sheet1": pd.read_csv(file_path)}
        else:
            sheets = pd.read_excel(file_path, sheet_name=None)
        
        all_chunks = []
        for sheet_name, df in sheets.items():
            all_chunks.extend(self._process_sheet(sheet_name, df))
        
        return all_chunks
    
    def _process_sheet(self, sheet_name: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        chunks = []
        df = df.fillna("")
        columns = df.columns.tolist()
        
        # 表级描述
        table_desc = f"工作表'{sheet_name}'包含列: {', '.join(str(c) for c in columns)}。共{len(df)}行数据。"
        chunks.append({
            "content": table_desc,
            "modality": "table",
            "chunk_index": 0,
            "position_info": {"type": "excel", "sheet_name": sheet_name, "columns": columns, "level": "table"},
            "metadata": {},
        })
        
        # 列级
        for i, col in enumerate(columns):
            samples = df[col].astype(str).head(5).tolist()
            col_text = f"工作表'{sheet_name}'的列'{col}'，样本值: {', '.join(str(s) for s in samples)}。"
            chunks.append({
                "content": col_text,
                "modality": "table",
                "chunk_index": i + 1,
                "position_info": {"type": "excel", "sheet_name": sheet_name, "columns": [col], "level": "column"},
                "metadata": {},
            })
        
        # 行级
        rows_per_chunk = 5
        for i in range(0, len(df), rows_per_chunk):
            row_df = df.iloc[i:i+rows_per_chunk]
            row_texts = []
            for _, row in row_df.iterrows():
                row_texts.append("; ".join([f"{col}: {row[col]}" for col in columns]))
            row_text = "\n".join(row_texts)
            
            chunks.append({
                "content": row_text,
                "modality": "table",
                "chunk_index": 100 + i,
                "position_info": {
                    "type": "excel",
                    "sheet_name": sheet_name,
                    "columns": columns,
                    "row_start": i,
                    "row_end": min(i + rows_per_chunk - 1, len(df) - 1),
                    "level": "row",
                },
                "metadata": {},
            })
        
        return chunks
