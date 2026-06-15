import os
from typing import List, Dict, Any
from uuid import UUID
from app.pipelines.base import BaseIngestPipeline

class VideoIngestPipeline(BaseIngestPipeline):
    """处理视频：当前阶段仅标记存储，不参与检索"""
    
    @property
    def supported_types(self) -> List[str]:
        return ["video"]
    
    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        return [{
            "content": "[视频内容待处理]",
            "modality": "video",
            "chunk_index": 0,
            "position_info": {
                "type": "video",
                "file_name": os.path.basename(file_path),
                "original_path": file_path,
                "status": "stored_only",
            },
            "metadata": {},
        }]
