"""Tests for the health check endpoint."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_all_ok(client):
    with patch("app.api.v1.health._check_postgres") as mock_pg, \
         patch("app.api.v1.health._check_redis") as mock_redis, \
         patch("app.api.v1.health._check_broker") as mock_broker, \
         patch("app.api.v1.health._check_vector_store") as mock_vector_store, \
         patch("app.api.v1.health._check_storage") as mock_storage:

        mock_pg.return_value = {"status": "ok", "latency_ms": 1.1}
        mock_redis.return_value = {"status": "ok", "latency_ms": 2.2}
        mock_broker.return_value = {"status": "ok", "latency_ms": 3.3}
        mock_vector_store.return_value = {"status": "ok", "latency_ms": 4.4}
        mock_storage.return_value = {"status": "ok", "latency_ms": 5.5}

        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    for service in ("postgres", "redis", "broker", "vector_store", "storage"):
        assert data["services"][service]["status"] == "ok"
        assert "latency_ms" in data["services"][service]


def test_health_degraded(client):
    with patch("app.api.v1.health._check_postgres") as mock_pg, \
         patch("app.api.v1.health._check_redis") as mock_redis, \
         patch("app.api.v1.health._check_broker") as mock_broker, \
         patch("app.api.v1.health._check_vector_store") as mock_vector_store, \
         patch("app.api.v1.health._check_storage") as mock_storage:

        mock_pg.return_value = {"status": "unavailable", "error": "pg down"}
        mock_redis.return_value = {"status": "unavailable", "error": "redis down"}
        mock_broker.return_value = {"status": "unavailable", "error": "broker down"}
        mock_vector_store.return_value = {"status": "unavailable", "error": "vector store down"}
        mock_storage.return_value = {"status": "unavailable", "error": "storage down"}

        response = client.get("/api/v1/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    for service in ("postgres", "redis", "broker", "vector_store", "storage"):
        assert data["services"][service]["status"] == "unavailable"
