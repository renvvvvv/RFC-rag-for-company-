import os
from typing import List, Dict, Any
from uuid import UUID
from app.pipelines.base import BaseIngestPipeline

class ImageIngestPipeline(BaseIngestPipeline):
    """处理图片：生成描述文本Chunk，原始图片存MinIO由DocumentService处理"""
    
    @property
    def supported_types(self) -> List[str]:
        return ["image"]
    
    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        image_description = metadata.get("description") or "图片内容"
        
        return [{
            "content": image_description,
            "modality": "image",
            "chunk_index": 0,
            "position_info": {
                "type": "image",
                "file_name": os.path.basename(file_path),
                "original_path": file_path,
            },
            "metadata": {"image_url": metadata.get("image_url")},
        }]
