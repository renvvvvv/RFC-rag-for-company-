"""Tests for collaboration service, schemas and API endpoints."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import collaboration as collab_api
from app.core.exceptions import NotFoundException, PermissionDeniedException
from app.schemas.collaboration import (
    BookmarkCreate,
    CommentCreate,
    CommentUpdate,
)
from app.services.collaboration_service import CollaborationService


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


def _make_comment(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "user_id": FAKE_USER.id,
        "target_type": "document",
        "target_id": uuid.uuid4(),
        "content": "Nice doc",
        "parent_id": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_bookmark(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "user_id": FAKE_USER.id,
        "target_type": "document",
        "target_id": uuid.uuid4(),
        "note": "Read later",
        "created_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------
def test_comment_create_valid():
    target_id = uuid.uuid4()
    payload = CommentCreate(
        target_type="document",
        target_id=target_id,
        content="Looks good",
    )
    assert payload.target_type == "document"
    assert payload.target_id == target_id
    assert payload.content == "Looks good"
    assert payload.parent_id is None


def test_comment_create_invalid_target_type():
    with pytest.raises(ValueError):
        CommentCreate(
            target_type="kb",
            target_id=uuid.uuid4(),
            content="content",
        )


def test_comment_create_empty_content():
    with pytest.raises(ValueError):
        CommentCreate(
            target_type="document",
            target_id=uuid.uuid4(),
            content="",
        )


def test_bookmark_create_valid():
    target_id = uuid.uuid4()
    payload = BookmarkCreate(
        target_type="chunk",
        target_id=target_id,
        note="Important",
    )
    assert payload.target_type == "chunk"
    assert payload.target_id == target_id
    assert payload.note == "Important"


# ------------------------------------------------------------------
# Service tests (with mocked async session)
# ------------------------------------------------------------------
@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_comment(mock_db):
    service = CollaborationService(mock_db)
    data = CommentCreate(
        target_type="document",
        target_id=uuid.uuid4(),
        content="hello",
    )
    comment = await service.create_comment(data, FAKE_USER.id)
    assert comment.target_type == "document"
    assert comment.content == "hello"
    assert comment.user_id == FAKE_USER.id
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(comment)


@pytest.mark.asyncio
async def test_list_comments_by_target(mock_db):
    service = CollaborationService(mock_db)
    target_id = uuid.uuid4()
    comments = [
        _make_comment(target_id=target_id),
        _make_comment(target_id=target_id),
    ]
    result_mock = AsyncMock()
    mock_db.execute.return_value = result_mock
    scalars_result = MagicMock()
    scalars_result.all.return_value = comments
    result_mock.scalars = MagicMock(return_value=scalars_result)

    items = await service.list_comments_by_target("document", target_id)
    assert len(items) == 2
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_comment_unauthorized(mock_db):
    service = CollaborationService(mock_db)
    comment = _make_comment(user_id=uuid.uuid4())
    mock_db.get.return_value = comment

    with pytest.raises(PermissionDeniedException):
        await service.update_comment(comment.id, FAKE_USER.id, "changed")


@pytest.mark.asyncio
async def test_delete_comment_not_found(mock_db):
    service = CollaborationService(mock_db)
    mock_db.get.return_value = None

    with pytest.raises(NotFoundException):
        await service.delete_comment(uuid.uuid4(), FAKE_USER.id)


@pytest.mark.asyncio
async def test_create_bookmark_idempotent(mock_db):
    service = CollaborationService(mock_db)
    data = BookmarkCreate(target_type="chunk", target_id=uuid.uuid4())
    existing = _make_bookmark()

    result_mock = AsyncMock()
    mock_db.execute.return_value = result_mock
    result_mock.scalar_one_or_none = MagicMock(return_value=existing)

    bookmark = await service.create_bookmark(data, FAKE_USER.id)
    assert bookmark is existing
    mock_db.add.assert_not_called()


# ------------------------------------------------------------------
# API tests (with mocked service and auth)
# ------------------------------------------------------------------
@pytest.fixture
def api_client(mock_service):
    app = FastAPI()
    app.include_router(collab_api.router, prefix="/api/v1")
    app.dependency_overrides[collab_api.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[collab_api.get_collaboration_service] = (
        lambda: mock_service
    )
    return TestClient(app)


@pytest.fixture
def mock_service():
    return AsyncMock()


def test_api_create_comment(api_client, mock_service):
    target_id = uuid.uuid4()
    comment = _make_comment(target_id=target_id)
    mock_service.create_comment.return_value = comment

    resp = api_client.post(
        "/api/v1/comments",
        json={"target_type": "document", "target_id": str(target_id), "content": "hello"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Nice doc"
    assert data["target_id"] == str(target_id)


def test_api_list_comments(api_client, mock_service):
    target_id = uuid.uuid4()
    mock_service.list_comments_by_target.return_value = [
        _make_comment(target_id=target_id),
        _make_comment(target_id=target_id, parent_id=uuid.uuid4()),
    ]

    resp = api_client.get(
        f"/api/v1/comments?target_type=document&target_id={target_id}"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_api_update_comment(api_client, mock_service):
    comment_id = uuid.uuid4()
    mock_service.update_comment.return_value = _make_comment(
        id=comment_id, content="updated"
    )

    resp = api_client.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": "updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "updated"


def test_api_create_bookmark(api_client, mock_service):
    target_id = uuid.uuid4()
    mock_service.create_bookmark.return_value = _make_bookmark(target_id=target_id)

    resp = api_client.post(
        "/api/v1/bookmarks",
        json={"target_type": "document", "target_id": str(target_id)},
    )
    assert resp.status_code == 201
    assert resp.json()["target_id"] == str(target_id)


def test_api_list_bookmarks(api_client, mock_service):
    mock_service.list_bookmarks_for_user.return_value = [
        _make_bookmark(),
        _make_bookmark(),
    ]

    resp = api_client.get("/api/v1/bookmarks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_api_delete_bookmark(api_client, mock_service):
    bookmark_id = uuid.uuid4()
    resp = api_client.delete(f"/api/v1/bookmarks/{bookmark_id}")
    assert resp.status_code == 204
    mock_service.delete_bookmark.assert_awaited_once_with(bookmark_id, FAKE_USER.id)
