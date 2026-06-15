"""Integration tests for search history recording and retrieval."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import search as search_api
from app.schemas.search import SearchRequest, SearchResultItem


FAKE_USER = SimpleNamespace(
    id=uuid.uuid4(),
    username="alice",
    email="alice@example.com",
    display_name="Alice",
    department="Engineering",
    security_level="L0",
    status="active",
    is_active=True,
)

KB_ID = uuid.uuid4()


def _make_history_item(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "user_id": FAKE_USER.id,
        "query": "test query",
        "mode": "hybrid",
        "kb_ids": [str(KB_ID)],
        "result_count": 2,
        "created_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def api_client(mock_db):
    app = FastAPI()
    app.include_router(search_api.router, prefix="/api/v1")
    app.dependency_overrides[search_api.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[search_api.get_db] = lambda: mock_db
    return TestClient(app)


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------
def test_search_request_schema_valid():
    req = SearchRequest(
        query="enterprise rag",
        kb_ids=[KB_ID],
        mode="hybrid",
        top_k=10,
        rerank_top_k=5,
    )
    assert req.query == "enterprise rag"
    assert req.mode == "hybrid"


def test_search_request_schema_invalid_mode():
    with pytest.raises(ValueError):
        SearchRequest(query="test", kb_ids=[KB_ID], mode="invalid")


def test_search_result_item_includes_position_info():
    item = SearchResultItem(
        chunk_id="chunk-1",
        doc_id="doc-1",
        content="context",
        modality="text",
        score=0.95,
        position_info={"page": 3, "bbox": [0, 0, 100, 100]},
    )
    assert item.position_info["page"] == 3


# ------------------------------------------------------------------
# API tests
# ------------------------------------------------------------------
@patch("app.api.v1.search.retrieval_service")
def test_api_search_records_history(mock_retrieval, api_client, mock_db):
    mock_retrieval.search = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-1",
                "content": "relevant text",
                "modality": "text",
                "score": 0.9,
                "position_info": {"page": 1},
            }
        ]
    )

    payload = {
        "query": "enterprise rag",
        "kb_ids": [str(KB_ID)],
        "mode": "hybrid",
        "top_k": 5,
        "rerank_top_k": 3,
    }
    resp = api_client.post("/api/v1/search/", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "enterprise rag"
    assert data["total"] == 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@patch("app.api.v1.search.retrieval_service")
def test_api_semantic_search_records_history(mock_retrieval, api_client, mock_db):
    mock_retrieval.semantic_search = AsyncMock(return_value=[])

    payload = {
        "query": "semantic only",
        "kb_ids": [str(KB_ID)],
        "mode": "semantic",
    }
    resp = api_client.post("/api/v1/search/semantic", json=payload)

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    mock_db.add.assert_called_once()


@patch("app.api.v1.search.retrieval_service")
def test_api_keyword_search_records_history(mock_retrieval, api_client, mock_db):
    mock_retrieval.keyword_search = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-2",
                "doc_id": "doc-2",
                "content": "keyword hit",
                "modality": "text",
                "score": 0.8,
            }
        ]
    )

    payload = {
        "query": "keyword query",
        "kb_ids": [str(KB_ID)],
        "mode": "keyword",
    }
    resp = api_client.post("/api/v1/search/keyword", json=payload)

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    mock_db.add.assert_called_once()


@patch("app.api.v1.search.retrieval_service")
def test_api_search_history_persistence_failure_is_non_fatal(
    mock_retrieval, api_client, mock_db
):
    mock_retrieval.search = AsyncMock(
        return_value=[{"chunk_id": "c1", "doc_id": "d1", "content": "x"}]
    )
    mock_db.commit.side_effect = Exception("db busy")

    payload = {
        "query": "history fails",
        "kb_ids": [str(KB_ID)],
        "mode": "hybrid",
    }
    resp = api_client.post("/api/v1/search/", json=payload)

    assert resp.status_code == 200
    mock_db.rollback.assert_awaited_once()


def test_api_get_search_history(api_client, mock_db):
    items = [
        _make_history_item(query="query one", mode="hybrid"),
        _make_history_item(query="query two", mode="semantic"),
    ]
    result_mock = AsyncMock()
    mock_db.execute.return_value = result_mock
    scalars_result = MagicMock()
    scalars_result.all.return_value = items
    result_mock.scalars = MagicMock(return_value=scalars_result)

    resp = api_client.get("/api/v1/search/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["items"][0]["query"] == "query one"


def test_api_get_search_history_with_mode_filter(api_client, mock_db):
    items = [_make_history_item(query="semantic query", mode="semantic")]
    result_mock = AsyncMock()
    mock_db.execute.return_value = result_mock
    scalars_result = MagicMock()
    scalars_result.all.return_value = items
    result_mock.scalars = MagicMock(return_value=scalars_result)

    resp = api_client.get("/api/v1/search/history?mode=semantic")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["mode"] == "semantic"


@patch("app.api.v1.search.retrieval_service")
def test_api_search_result_includes_position_info(mock_retrieval, api_client, mock_db):
    mock_retrieval.search = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-1",
                "content": "text",
                "modality": "text",
                "score": 0.9,
                "position_info": {"page": 2, "paragraph": 5},
            }
        ]
    )

    payload = {
        "query": "with citation",
        "kb_ids": [str(KB_ID)],
        "mode": "hybrid",
    }
    resp = api_client.post("/api/v1/search/", json=payload)

    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["position_info"]["page"] == 2
    assert result["position_info"]["paragraph"] == 5
