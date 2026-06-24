"""Integration tests for citation / position_info in retrieval and chat."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import chat as chat_api
from app.api.v1 import search as search_api
from app.schemas.chat import SourceItem
from app.schemas.search import SearchRequest, SearchResultItem
from app.services.generation_service import GenerationService
from app.services.retrieval_service import RetrievalService


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
CONVERSATION_ID = uuid.uuid4()


CHUNK_ID = str(uuid.uuid4())
DOC_ID = str(uuid.uuid4())


def _chunk_with_position(**overrides):
    defaults = {
        "chunk_id": CHUNK_ID,
        "doc_id": DOC_ID,
        "content": "relevant content",
        "modality": "text",
        "score": 0.95,
        "rerank_score": 0.92,
        "position_info": {"page": 2, "paragraph": 3, "bbox": [10, 20, 100, 200]},
    }
    defaults.update(overrides)
    return defaults


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def search_client():
    app = FastAPI()
    app.include_router(search_api.router, prefix="/api/v1")
    app.dependency_overrides[search_api.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[search_api.get_db] = _make_mock_db
    return TestClient(app)


@pytest.fixture
def chat_client():
    app = FastAPI()
    app.include_router(chat_api.router, prefix="/api/v1")
    app.dependency_overrides[chat_api.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[chat_api.get_db] = lambda: AsyncMock()
    return TestClient(app)


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------
def test_search_result_item_carries_position_info():
    item = SearchResultItem(
        chunk_id="c1",
        doc_id="d1",
        content="text",
        modality="text",
        score=0.9,
        position_info={"page": 1, "sheet": "Sheet1", "cell": "B2"},
    )
    assert item.position_info["sheet"] == "Sheet1"
    assert item.position_info["cell"] == "B2"


def test_source_item_schema():
    source = SourceItem(
        doc_id="d1",
        chunk_id="c1",
        content="context",
        score=0.9,
        modality="text",
    )
    assert source.doc_id == "d1"


# ------------------------------------------------------------------
# Search API tests
# ------------------------------------------------------------------
@patch("app.api.v1.search.retrieval_service")
def test_search_api_returns_position_info(mock_retrieval, search_client):
    mock_retrieval.search = AsyncMock(return_value=[_chunk_with_position()])

    resp = search_client.post(
        "/api/v1/search/",
        json={
            "query": "citation test",
            "kb_ids": [str(KB_ID)],
            "mode": "hybrid",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    result = data["results"][0]
    assert result["position_info"]["page"] == 2
    assert result["position_info"]["paragraph"] == 3


@patch("app.api.v1.search.retrieval_service")
def test_semantic_search_api_returns_position_info(mock_retrieval, search_client):
    mock_retrieval.semantic_search = AsyncMock(
        return_value=[_chunk_with_position(position_info={"sheet": "Sheet1", "row": 5})]
    )

    resp = search_client.post(
        "/api/v1/search/semantic",
        json={"query": "semantic citation", "kb_ids": [str(KB_ID)]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["position_info"]["sheet"] == "Sheet1"


@patch("app.api.v1.search.retrieval_service")
def test_keyword_search_api_returns_position_info(mock_retrieval, search_client):
    mock_retrieval.keyword_search = AsyncMock(
        return_value=[_chunk_with_position(position_info={"timestamp": 12.5})]
    )

    resp = search_client.post(
        "/api/v1/search/keyword",
        json={"query": "keyword citation", "kb_ids": [str(KB_ID)]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["position_info"]["timestamp"] == 12.5


# ------------------------------------------------------------------
# Chat API tests
# ------------------------------------------------------------------
@patch("app.api.v1.chat.retrieval_service")
@patch("app.api.v1.chat.security_gateway")
@patch("app.api.v1.chat.generation_service")
@patch("app.api.v1.chat.conversation_service")
def test_chat_api_sources_include_position_info(
    mock_conv_service, mock_gen_service, mock_security, mock_retrieval, chat_client
):
    mock_retrieval.search = AsyncMock(return_value=[_chunk_with_position()])
    mock_security.detect_prompt_injection.return_value = False
    mock_security._fast_level_check = AsyncMock(return_value=None)
    mock_security.decide_api_strategy = AsyncMock(
        return_value={
            "strategy": "direct_api",
            "max_level": 0,
            "reason": "可直接调用外部API",
        }
    )
    mock_gen_service.generate_answer = AsyncMock(
        return_value={
            "answer": "answer with citation",
            "intercepted": False,
            "sources": [
                {
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "content": "relevant content",
                    "score": 0.92,
                    "modality": "text",
                    "position_info": {"page": 2, "paragraph": 3},
                }
            ],
        }
    )

    resp = chat_client.post(
        "/api/v1/chat/",
        json={"query": "where is the info?", "kb_ids": [str(KB_ID)]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) == 1


@patch("app.api.v1.chat.retrieval_service")
@patch("app.api.v1.chat.security_gateway")
@patch("app.api.v1.chat.generation_service")
@patch("app.api.v1.chat.conversation_service")
def test_chat_api_sources_expose_position_info(
    mock_conv_service, mock_gen_service, mock_security, mock_retrieval, chat_client
):
    mock_retrieval.search = AsyncMock(return_value=[_chunk_with_position()])
    mock_security.detect_prompt_injection.return_value = False
    mock_security._fast_level_check = AsyncMock(return_value=None)
    mock_security.decide_api_strategy = AsyncMock(
        return_value={
            "strategy": "direct_api",
            "max_level": 0,
            "reason": "可直接调用外部API",
        }
    )
    mock_gen_service.generate_answer = AsyncMock(
        return_value={
            "answer": "answer with citation",
            "intercepted": False,
            "sources": [
                {
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "content": "relevant content",
                    "score": 0.92,
                    "modality": "text",
                    "position_info": {"page": 2, "paragraph": 3},
                }
            ],
        }
    )

    resp = chat_client.post(
        "/api/v1/chat/",
        json={"query": "where is the info?", "kb_ids": [str(KB_ID)]},
    )

    data = resp.json()
    assert "position_info" in data["sources"][0]
    assert data["sources"][0]["position_info"]["page"] == 2


# ------------------------------------------------------------------
# Service-level tests
# ------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.retrieval_service.PermissionService")
@patch("app.services.retrieval_service.embedding_client")
@patch("app.services.retrieval_service.get_vector_store")
@patch("app.services.retrieval_service.bm25_client")
@patch("app.services.retrieval_service.rerank_client")
async def test_retrieval_service_preserves_position_info(
    mock_rerank, mock_bm25, mock_get_vector_store, mock_embedding, MockPermissionService
):
    from app.models.chunk import Chunk
    from app.retrieval.filters import VectorFilter

    mock_perm_service = AsyncMock()
    mock_perm_service.get_user_security_level.return_value = "L0"
    mock_perm_service.get_user_denied_documents.return_value = set()
    mock_perm_service.get_user_denied_tags.return_value = set()
    mock_perm_service.get_user_allowed_file_types.return_value = set()
    mock_perm_service.build_vector_filter.return_value = VectorFilter(
        kb_ids=[], modalities=[], denied_doc_ids=[], denied_tags=[], status="active"
    )
    mock_perm_service.check_field_permission.return_value = True
    MockPermissionService.return_value = mock_perm_service

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_vector_store = MagicMock()
    mock_vector_store.backend_name = "milvus"
    mock_vector_store.search_text.return_value = [
        {"chunk_id": str(chunk_id), "score": 0.9}
    ]
    mock_get_vector_store.return_value = mock_vector_store

    mock_embedding.embed = AsyncMock(return_value=[0.1, 0.2])
    mock_bm25.search = AsyncMock(return_value=[])
    mock_rerank.rerank = AsyncMock(
        return_value=[
            {
                "chunk_id": str(chunk_id),
                "doc_id": str(doc_id),
                "content": "content",
                "modality": "text",
                "score": 0.9,
                "position_info": {"page": 5},
            }
        ]
    )

    db = AsyncMock()
    chunk = Chunk(
        id=chunk_id,
        doc_id=doc_id,
        content="content",
        chunk_index=0,
        position_info={"page": 5},
        metadata_={},
    )

    execute_result = AsyncMock()
    db.execute.return_value = execute_result
    scalars_result = MagicMock()
    scalars_result.all.return_value = [chunk]
    execute_result.scalars = MagicMock(return_value=scalars_result)

    service = RetrievalService()
    results = await service.search(
        db=db,
        user_id=FAKE_USER.id,
        query="q",
        kb_ids=[KB_ID],
    )

    assert len(results) == 1
    assert results[0]["position_info"]["page"] == 5


@pytest.mark.asyncio
@patch("app.services.generation_service.KeywordService")
async def test_generation_service_post_process_includes_position_info(MockKeywordService):
    mock_keyword_service = AsyncMock()
    intercept_result = SimpleNamespace(allowed=True, message=None)
    mock_keyword_service.intercept_response.return_value = intercept_result
    MockKeywordService.return_value = mock_keyword_service

    chunk_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    service = GenerationService()
    chunks = [
        {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "content": "context text",
            "modality": "text",
            "score": 0.9,
            "position_info": {"page": 7, "heading_path": "Section 1"},
        }
    ]

    result = await service._post_process(
        db=AsyncMock(),
        answer="answer",
        context_chunks=chunks,
        user_id=FAKE_USER.id,
    )

    assert result["intercepted"] is False
    assert len(result["sources"]) == 1
    assert result["sources"][0]["position_info"]["page"] == 7
    assert result["sources"][0]["page"] == 7
