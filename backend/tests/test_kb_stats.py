"""Integration tests for knowledge base statistics endpoint."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.v1 import knowledge_bases as kb_api
from app.api.v1.auth import get_current_user
from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseStats
from app.schemas.user import UserResponse


KB_ID = uuid.uuid4()
FAKE_USER_ID = uuid.uuid4()


def _make_current_user():
    return UserResponse(
        id=FAKE_USER_ID,
        username="alice",
        email="alice@example.com",
        display_name="Alice",
        department="Engineering",
        security_level="L2",
        status="active",
        is_active=True,
    )


def _make_kb(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": KB_ID,
        "name": "Test KB",
        "description": "A test knowledge base",
        "config": {},
        "status": "active",
        "owner_id": FAKE_USER_ID,
        "created_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def api_client(mock_db):
    app = FastAPI()
    app.include_router(kb_api.router, prefix="/api/v1")
    app.dependency_overrides[kb_api.get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = _make_current_user

    @app.exception_handler(NotFoundException)
    async def not_found_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": exc.message})

    return TestClient(app)


def _scalar_result(value):
    mock = MagicMock()
    mock.scalar.return_value = value
    return mock


def _tuple_result(rows):
    mock = MagicMock()
    mock.all.return_value = rows
    return mock


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------
def test_knowledge_base_stats_schema():
    stats = KnowledgeBaseStats(
        kb_id=KB_ID,
        document_count=5,
        chunk_count=42,
        status_breakdown={"indexed": 3, "pending": 2},
        last_upload_at=datetime.now(timezone.utc),
    )
    assert stats.document_count == 5
    assert stats.chunk_count == 42


# ------------------------------------------------------------------
# API tests
# ------------------------------------------------------------------
def test_api_get_kb_stats(api_client, mock_db):
    mock_db.get.return_value = _make_kb()

    execute_side_effects = [
        _scalar_result(5),  # document_count
        _tuple_result([("indexed", 3), ("pending", 2)]),  # status breakdown
        _scalar_result(42),  # chunk_count
        _scalar_result(datetime.now(timezone.utc)),  # last_upload_at
    ]
    mock_db.execute.side_effect = execute_side_effects

    resp = api_client.get(f"/api/v1/knowledge-bases/{KB_ID}/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["kb_id"] == str(KB_ID)
    assert data["document_count"] == 5
    assert data["chunk_count"] == 42
    assert data["status_breakdown"]["indexed"] == 3
    assert data["status_breakdown"]["pending"] == 2
    assert "last_upload_at" in data


def test_api_get_kb_stats_empty_documents(api_client, mock_db):
    mock_db.get.return_value = _make_kb()

    execute_side_effects = [
        _scalar_result(0),
        _tuple_result([]),
        _scalar_result(0),
        _scalar_result(None),
    ]
    mock_db.execute.side_effect = execute_side_effects

    resp = api_client.get(f"/api/v1/knowledge-bases/{KB_ID}/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["document_count"] == 0
    assert data["chunk_count"] == 0
    assert data["status_breakdown"] == {}
    assert data["last_upload_at"] is None


def test_api_get_kb_stats_not_found(api_client, mock_db):
    mock_db.get.return_value = None

    resp = api_client.get(f"/api/v1/knowledge-bases/{KB_ID}/stats")

    assert resp.status_code == 404
    mock_db.execute.assert_not_awaited()


def test_api_get_kb_stats_status_breakdown(api_client, mock_db):
    mock_db.get.return_value = _make_kb()

    execute_side_effects = [
        _scalar_result(4),
        _tuple_result([("failed", 1), ("processing", 1), ("indexed", 2)]),
        _scalar_result(10),
        _scalar_result(datetime.now(timezone.utc)),
    ]
    mock_db.execute.side_effect = execute_side_effects

    resp = api_client.get(f"/api/v1/knowledge-bases/{KB_ID}/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["document_count"] == 4
    assert data["status_breakdown"]["failed"] == 1
    assert data["status_breakdown"]["processing"] == 1
    assert data["status_breakdown"]["indexed"] == 2


def test_api_get_kb_stats_queries_document_and_chunk_tables(api_client, mock_db):
    mock_db.get.return_value = _make_kb()
    mock_db.execute.side_effect = [
        _scalar_result(1),
        _tuple_result([("indexed", 1)]),
        _scalar_result(3),
        _scalar_result(datetime.now(timezone.utc)),
    ]

    api_client.get(f"/api/v1/knowledge-bases/{KB_ID}/stats")

    assert mock_db.execute.await_count == 4
