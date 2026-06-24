"""Integration tests for chat, conversation, and message feedback APIs."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import chat as chat_api
from app.schemas.chat import ChatRequest, ConversationCreate, FeedbackCreate


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
MESSAGE_ID = uuid.uuid4()


def _make_conversation(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": CONVERSATION_ID,
        "user_id": FAKE_USER.id,
        "title": "Test conversation",
        "kb_ids": [str(KB_ID)],
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_message(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": MESSAGE_ID,
        "conversation_id": CONVERSATION_ID,
        "role": "assistant",
        "content": "hello",
        "sources": [],
        "feedback_rating": None,
        "feedback_comment": None,
        "created_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(chat_api.router, prefix="/api/v1")
    app.dependency_overrides[chat_api.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[chat_api.get_db] = lambda: AsyncMock()
    return TestClient(app)


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------
def test_conversation_create_schema():
    schema = ConversationCreate(title="New chat", kb_ids=[KB_ID])
    assert schema.title == "New chat"
    assert schema.kb_ids == [KB_ID]


def test_feedback_create_schema_valid():
    schema = FeedbackCreate(rating=1, comment="helpful")
    assert schema.rating == 1


def test_feedback_create_schema_invalid_rating():
    with pytest.raises(ValueError):
        FeedbackCreate(rating=5)


def test_chat_request_schema():
    schema = ChatRequest(query="hi", kb_ids=[KB_ID], conversation_id=CONVERSATION_ID)
    assert schema.query == "hi"
    assert schema.conversation_id == CONVERSATION_ID


# ------------------------------------------------------------------
# API tests
# ------------------------------------------------------------------
@patch("app.api.v1.chat.conversation_service")
def test_api_create_conversation(mock_conv_service, api_client):
    mock_conv_service.create_conversation = AsyncMock(
        return_value=_make_conversation()
    )

    resp = api_client.post(
        "/api/v1/chat/conversations",
        json={"title": "New chat", "kb_ids": [str(KB_ID)]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test conversation"
    assert data["user_id"] == str(FAKE_USER.id)
    mock_conv_service.create_conversation.assert_awaited_once()


@patch("app.api.v1.chat.conversation_service")
def test_api_list_conversations(mock_conv_service, api_client):
    mock_conv_service.list_conversations = AsyncMock(
        return_value=[
            _make_conversation(title="First"),
            _make_conversation(title="Second"),
        ]
    )

    resp = api_client.get("/api/v1/chat/conversations")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "First"


@patch("app.api.v1.chat.retrieval_service")
@patch("app.api.v1.chat.security_gateway")
@patch("app.api.v1.chat.generation_service")
@patch("app.api.v1.chat.conversation_service")
def test_api_chat_full_flow(
    mock_conv_service, mock_gen_service, mock_security, mock_retrieval, api_client
):
    mock_conv_service.get_conversation = AsyncMock(
        return_value=_make_conversation()
    )
    mock_conv_service.build_history_messages = AsyncMock(return_value=[])
    mock_conv_service.add_message = AsyncMock(return_value=_make_message())

    mock_retrieval.search = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-1",
                "content": "context",
                "modality": "text",
                "score": 0.9,
                "max_keyword_level": "L0",
            }
        ]
    )
    mock_security.detect_prompt_injection.return_value = False
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
            "answer": "This is the answer.",
            "intercepted": False,
            "sources": [
                {
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "content": "context",
                    "score": 0.9,
                    "modality": "text",
                }
            ],
        }
    )

    resp = api_client.post(
        "/api/v1/chat/",
        json={
            "query": "What is RAG?",
            "kb_ids": [str(KB_ID)],
            "conversation_id": str(CONVERSATION_ID),
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "This is the answer."
    assert data["intercepted"] is False
    assert len(data["sources"]) == 1
    mock_conv_service.add_message.assert_awaited()


@patch("app.api.v1.chat.retrieval_service")
@patch("app.api.v1.chat.security_gateway")
@patch("app.api.v1.chat.generation_service")
@patch("app.api.v1.chat.conversation_service")
def test_api_chat_local_only_intercepted(
    mock_conv_service, mock_gen_service, mock_security, mock_retrieval, api_client
):
    mock_retrieval.search = AsyncMock(return_value=[])
    mock_security.detect_prompt_injection.return_value = False
    mock_security._fast_level_check = AsyncMock(return_value=None)
    mock_security.decide_api_strategy = AsyncMock(
        return_value={
            "strategy": "local_only",
            "max_level": 4,
            "reason": "绝密内容禁止调用外部API",
        }
    )

    resp = api_client.post(
        "/api/v1/chat/",
        json={"query": "secret", "kb_ids": [str(KB_ID)]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "绝密" in data["answer"]
    assert data["intercepted"] is True
    mock_gen_service.generate_answer.assert_not_called()


@patch("app.api.v1.chat.conversation_service")
def test_api_add_feedback(mock_conv_service, api_client):
    mock_conv_service.update_feedback = AsyncMock(
        return_value=_make_message(
            feedback_rating=1,
            feedback_comment="good",
        )
    )

    resp = api_client.post(
        f"/api/v1/chat/messages/{MESSAGE_ID}/feedback",
        json={"rating": 1, "comment": "good"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["feedback_rating"] == 1
    assert data["feedback_comment"] == "good"
    mock_conv_service.update_feedback.assert_awaited_once()
    call_kwargs = mock_conv_service.update_feedback.await_args.kwargs
    assert call_kwargs["message_id"] == MESSAGE_ID
    assert call_kwargs["user_id"] == FAKE_USER.id
    assert call_kwargs["rating"] == 1
    assert call_kwargs["comment"] == "good"


@patch("app.api.v1.chat.conversation_service")
def test_api_add_feedback_not_found(mock_conv_service, api_client):
    mock_conv_service.update_feedback = AsyncMock(return_value=None)

    resp = api_client.post(
        f"/api/v1/chat/messages/{MESSAGE_ID}/feedback",
        json={"rating": -1},
    )

    assert resp.status_code == 404


@patch("app.api.v1.chat.conversation_service")
def test_api_get_messages(mock_conv_service, api_client):
    mock_conv_service.get_conversation = AsyncMock(
        return_value=_make_conversation()
    )
    mock_conv_service.get_messages = AsyncMock(
        return_value=[
            _make_message(role="user", content="hello"),
            _make_message(role="assistant", content="hi there"),
        ]
    )

    resp = api_client.get(f"/api/v1/chat/conversations/{CONVERSATION_ID}/messages")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[1]["role"] == "assistant"
