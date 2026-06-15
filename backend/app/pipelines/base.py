from abc import ABC, abstractmethod
from typing import List, Dict, Any
from uuid import UUID

class BaseIngestPipeline(ABC):
    """文档摄取Pipeline抽象基类。返回dict列表，字段：
    content, modality, chunk_index, position_info, metadata
    """
    
    @property
    @abstractmethod
    def supported_types(self) -> List[str]:
        """支持的文件类型列表"""
        pass
    
    def can_process(self, file_type: str) -> bool:
        return file_type in self.supported_types
    
    @abstractmethod
    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        pass
