import pytest
from app.pipelines.keyword_annotator import KeywordAnnotator, LEVEL_ORDER
from app.models.chunk import Chunk


class MockKeyword:
    def __init__(self, keyword, level="L2", variants=None, apply_to_modalities=None):
        self.id = "mock-id"
        self.keyword = keyword
        self.level = level
        self.category = "test"
        self.match_type = "exact"
        self.variants = variants or []
        self.apply_to_modalities = apply_to_modalities or []
        self.action = "audit"


def test_keyword_annotator_basic():
    annotator = KeywordAnnotator()
    annotator.load_keywords([
        MockKeyword("机密", level="L3"),
        MockKeyword("公开", level="L0"),
    ])
    
    result = annotator.annotate("这份文件包含机密信息")
    assert result.max_level == "L3"
    assert len(result.matches) == 1
    assert result.matches[0].keyword == "机密"


def test_keyword_annotator_chunk():
    annotator = KeywordAnnotator()
    annotator.load_keywords([MockKeyword("薪资", level="L2")])
    
    chunk = Chunk(content="员工薪资信息")
    annotator.annotate_chunk(chunk)
    
    meta = chunk.metadata_
    assert meta["max_keyword_level"] == "L2"
    assert meta["max_keyword_level_value"] == LEVEL_ORDER["L2"]
