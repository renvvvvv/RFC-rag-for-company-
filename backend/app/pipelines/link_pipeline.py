from typing import List, Dict, Any
from uuid import UUID
from app.pipelines.base import BaseIngestPipeline

class LinkIngestPipeline(BaseIngestPipeline):
    """处理网页链接"""
    
    @property
    def supported_types(self) -> List[str]:
        return ["link"]
    
    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        url = metadata.get("url") or file_path
        title = metadata.get("title", "")
        content = metadata.get("content", "") or f"链接内容: {url}"
        
        chunk_text = f"标题: {title}\nURL: {url}\n正文: {content}"
        return [{
            "content": chunk_text[:2000],
            "modality": "text",
            "chunk_index": 0,
            "position_info": {"type": "link", "url": url, "title": title},
            "metadata": {},
        }]
