import pytest
from uuid import uuid4

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    FeedbackCreate,
    MessageResponse,
    SourceItem,
)
from app.services.conversation_service import ConversationService


def test_conversation_service_instantiation():
    service = ConversationService()
    assert service is not None


def test_conversation_create_schema():
    kb_id = uuid4()
    schema = ConversationCreate(title="测试会话", kb_ids=[kb_id])
    assert schema.title == "测试会话"
    assert schema.kb_ids == [kb_id]


def test_feedback_create_schema():
    schema = FeedbackCreate(rating=1, comment=" helpful")
    assert schema.rating == 1
    assert schema.comment == " helpful"

    with pytest.raises(ValueError):
        FeedbackCreate(rating=2)


def test_chat_request_with_conversation_id():
    kb_id = uuid4()
    conv_id = uuid4()
    schema = ChatRequest(
        query="你好",
        kb_ids=[kb_id],
        conversation_id=conv_id,
    )
    assert schema.conversation_id == conv_id
    assert schema.query == "你好"


def test_chat_request_backward_compatible():
    kb_id = uuid4()
    schema = ChatRequest(query="你好", kb_ids=[kb_id])
    assert schema.conversation_id is None
    assert schema.stream is False


def test_chat_response_schema():
    source = SourceItem(doc_id=None, chunk_id=None, content="ctx", score=0.9, modality="text")
    response = ChatResponse(
        answer="answer",
        sources=[source],
        conversation_id=uuid4(),
    )
    assert response.answer == "answer"
    assert len(response.sources) == 1
    assert response.conversation_id is not None


def test_message_response_schema():
    msg = MessageResponse(
        id=uuid4(),
        conversation_id=uuid4(),
        role="assistant",
        content="hello",
        sources=[],
        created_at="2024-01-01T00:00:00Z",
    )
    assert msg.role == "assistant"
    assert msg.feedback_rating is None


def test_conversation_response_schema():
    conv = ConversationResponse(
        id=uuid4(),
        user_id=uuid4(),
        title="t",
        kb_ids=[],
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    assert conv.title == "t"
