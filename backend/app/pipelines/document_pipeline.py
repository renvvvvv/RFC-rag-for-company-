import os
from typing import List, Dict, Any
from uuid import UUID
from app.pipelines.base import BaseIngestPipeline

class DocumentIngestPipeline(BaseIngestPipeline):
    """处理 doc/docx/pdf/txt/markdown 文档"""
    
    @property
    def supported_types(self) -> List[str]:
        return ["document", "pdf", "txt", "markdown"]
    
    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in [".docx", ".doc"]:
            text = self._extract_docx(file_path)
        elif ext == ".pdf":
            text = self._extract_pdf(file_path)
        elif ext in [".txt", ".md", ".markdown"]:
            text = self._extract_txt(file_path)
        else:
            text = ""
        
        return self._chunk_text(text)
    
    def _extract_docx(self, file_path: str) -> str:
        try:
            import docx
            doc = docx.Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception as e:
            return f"[解析失败: {str(e)}]"
    
    def _extract_pdf(self, file_path: str) -> str:
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        texts.append(text)
            return "\n".join(texts)
        except Exception as e:
            return f"[解析失败: {str(e)}]"
    
    def _extract_txt(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    
    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 100
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
