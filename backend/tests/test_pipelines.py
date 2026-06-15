import pytest
from uuid import uuid4
from app.pipelines.factory import PipelineFactory
from app.pipelines.document_pipeline import DocumentIngestPipeline
from app.pipelines.excel_pipeline import ExcelIngestPipeline


def test_pipeline_factory_document():
    pipeline = PipelineFactory.get_pipeline("pdf")
    assert isinstance(pipeline, DocumentIngestPipeline)


def test_pipeline_factory_excel():
    pipeline = PipelineFactory.get_pipeline("excel")
    assert isinstance(pipeline, ExcelIngestPipeline)


def test_document_pipeline_chunking():
    pipeline = DocumentIngestPipeline()
    # Create a temporary text file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello world. " * 100)
        path = f.name
    
    chunks = pipeline.process(path, uuid4())
    assert len(chunks) > 0
    assert "content" in chunks[0]
    assert chunks[0]["modality"] == "text"
