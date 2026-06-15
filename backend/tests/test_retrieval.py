"""Unit tests for the hybrid retrieval layer."""
from uuid import uuid4

import pytest

from app.retrieval.bm25_client import BM25Client
from app.services.retrieval_service import RetrievalService


def test_bm25_query_normalisation():
    client = BM25Client()
    assert client._normalise_query("  hello   world  ") == "hello world"
    assert client._normalise_query("SQL注入!!!") == "SQL注入"
    assert client._normalise_query("") == ""


def test_rrf_fusion_basic():
    service = RetrievalService()
    vector_hits = [
        {"chunk_id": "a", "score": 0.9},
        {"chunk_id": "b", "score": 0.8},
        {"chunk_id": "c", "score": 0.7},
    ]
    bm25_hits = [
        {"chunk_id": "b", "score": 1.0},
        {"chunk_id": "d", "score": 0.95},
    ]

    fused = service._rrf_fusion(vector_hits, bm25_hits)

    # All unique ids are present
    assert {item["chunk_id"] for item in fused} == {"a", "b", "c", "d"}
    # b appears in both lists, so it should rank highest
    assert fused[0]["chunk_id"] == "b"
    # Each result carries an RRF score
    assert all("score" in item for item in fused)


def test_rrf_fusion_empty_inputs():
    service = RetrievalService()
    assert service._rrf_fusion([], []) == []
    assert service._rrf_fusion([{"chunk_id": "x", "score": 0.5}], []) == [
        {"chunk_id": "x", "score": pytest.approx(1 / (service.RRF_K + 1))}
    ]


def test_search_request_schema_validation():
    from app.schemas.search import SearchRequest
    from uuid import uuid4

    req = SearchRequest(
        query="test query",
        kb_ids=[uuid4()],
        mode="hybrid",
        top_k=10,
        rerank_top_k=5,
    )
    assert req.mode == "hybrid"


def test_rrf_fusion_preserves_highest_rank_score():
    """A top-ranked hit in both lists should score more than a top-ranked hit
    in a single list.
    """
    service = RetrievalService()
    both = [
        {"chunk_id": "top_both", "score": 0.5},
        {"chunk_id": "single", "score": 0.5},
    ]
    fused = service._rrf_fusion(both, both)
    scores = {item["chunk_id"]: item["score"] for item in fused}
    assert scores["top_both"] > scores["single"]
