from typing import Optional
from app.pipelines.base import BaseIngestPipeline
from app.pipelines.document_pipeline import DocumentIngestPipeline
from app.pipelines.excel_pipeline import ExcelIngestPipeline
from app.pipelines.image_pipeline import ImageIngestPipeline
from app.pipelines.video_pipeline import VideoIngestPipeline
from app.pipelines.link_pipeline import LinkIngestPipeline

class PipelineFactory:
    """Pipeline工厂"""
    
    _pipelines = [
        DocumentIngestPipeline(),
        ExcelIngestPipeline(),
        ImageIngestPipeline(),
        VideoIngestPipeline(),
        LinkIngestPipeline(),
    ]
    
    @classmethod
    def get_pipeline(cls, file_type: str) -> Optional[BaseIngestPipeline]:
        for pipeline in cls._pipelines:
            if pipeline.can_process(file_type):
                return pipeline
        return None
