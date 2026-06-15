"""Integration tests for document reprocessing endpoint."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import documents as documents_api
from app.core.exceptions import NotFoundException, ValidationException


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

DOC_ID = uuid.uuid4()
KB_ID = uuid.uuid4()


def _make_document(status="indexed", **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": DOC_ID,
        "kb_id": KB_ID,
        "filename": "report.pdf",
        "file_type": "pdf",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "storage_key": f"{KB_ID}/report.pdf",
        "status": status,
        "processing_info": {"stage": "completed"},
        "metadata": {},
        "created_by": FAKE_USER.id,
        "created_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(documents_api.router, prefix="/api/v1")
    app.dependency_overrides[documents_api.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[documents_api.get_db] = lambda: AsyncMock()

    @app.exception_handler(NotFoundException)
    async def not_found_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(ValidationException)
    async def validation_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": exc.message})

    return TestClient(app)


# ------------------------------------------------------------------
# API tests
# ------------------------------------------------------------------
@patch("app.api.v1.documents.process_document")
@patch("app.api.v1.documents.DocumentService")
def test_api_reprocess_document_resets_status_and_triggers_task(
    MockService, mock_task, api_client
):
    mock_service = AsyncMock()
    mock_service.get_document.return_value = _make_document(status="indexed")
    mock_service.update_status.return_value = None
    MockService.return_value = mock_service

    resp = api_client.post(f"/api/v1/documents/{DOC_ID}/reprocess")

    assert resp.status_code == 200
    mock_service.update_status.assert_awaited_once_with(
        DOC_ID,
        status="pending",
        processing_info={"reprocess_requested_by": str(FAKE_USER.id)},
    )
    mock_task.delay.assert_called_once_with(str(DOC_ID))


@patch("app.api.v1.documents.process_document")
@patch("app.api.v1.documents.DocumentService")
def test_api_reprocess_while_processing_returns_400(
    MockService, mock_task, api_client
):
    mock_service = AsyncMock()
    mock_service.get_document.return_value = _make_document(status="processing")
    MockService.return_value = mock_service

    resp = api_client.post(f"/api/v1/documents/{DOC_ID}/reprocess")

    assert resp.status_code == 400
    mock_task.delay.assert_not_called()


@patch("app.api.v1.documents.process_document")
@patch("app.api.v1.documents.DocumentService")
def test_api_reprocess_nonexistent_document_returns_404(
    MockService, mock_task, api_client
):
    mock_service = AsyncMock()
    mock_service.get_document.side_effect = NotFoundException("文档不存在")
    MockService.return_value = mock_service

    resp = api_client.post(f"/api/v1/documents/{DOC_ID}/reprocess")

    assert resp.status_code == 404
    mock_task.delay.assert_not_called()


@patch("app.api.v1.documents.process_document")
@patch("app.api.v1.documents.DocumentService")
def test_api_reprocess_failed_document(MockService, mock_task, api_client):
    mock_service = AsyncMock()
    mock_service.get_document.return_value = _make_document(
        status="failed", processing_info={"error": "timeout"}
    )
    MockService.return_value = mock_service

    resp = api_client.post(f"/api/v1/documents/{DOC_ID}/reprocess")

    assert resp.status_code == 200
    mock_service.update_status.assert_awaited_once_with(
        DOC_ID,
        status="pending",
        processing_info={"reprocess_requested_by": str(FAKE_USER.id)},
    )
    mock_task.delay.assert_called_once_with(str(DOC_ID))


@patch("app.api.v1.documents.process_document")
@patch("app.api.v1.documents.DocumentService")
def test_api_reprocess_returns_document_response(MockService, mock_task, api_client):
    doc = _make_document(status="indexed")
    mock_service = AsyncMock()
    mock_service.get_document.return_value = doc
    MockService.return_value = mock_service

    resp = api_client.post(f"/api/v1/documents/{DOC_ID}/reprocess")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(DOC_ID)
    assert data["filename"] == "report.pdf"
