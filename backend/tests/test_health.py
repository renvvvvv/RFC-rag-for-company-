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
         patch("app.api.v1.health._check_rabbitmq") as mock_rabbit, \
         patch("app.api.v1.health._check_milvus") as mock_milvus, \
         patch("app.api.v1.health._check_minio") as mock_minio:

        mock_pg.return_value = {"status": "ok", "latency_ms": 1.1}
        mock_redis.return_value = {"status": "ok", "latency_ms": 2.2}
        mock_rabbit.return_value = {"status": "ok", "latency_ms": 3.3}
        mock_milvus.return_value = {"status": "ok", "latency_ms": 4.4}
        mock_minio.return_value = {"status": "ok", "latency_ms": 5.5}

        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    for service in ("postgres", "redis", "rabbitmq", "milvus", "minio"):
        assert data["services"][service]["status"] == "ok"
        assert "latency_ms" in data["services"][service]


def test_health_degraded(client):
    with patch("app.api.v1.health._check_postgres") as mock_pg, \
         patch("app.api.v1.health._check_redis") as mock_redis, \
         patch("app.api.v1.health._check_rabbitmq") as mock_rabbit, \
         patch("app.api.v1.health._check_milvus") as mock_milvus, \
         patch("app.api.v1.health._check_minio") as mock_minio:

        mock_pg.return_value = {"status": "unavailable", "error": "pg down"}
        mock_redis.return_value = {"status": "unavailable", "error": "redis down"}
        mock_rabbit.return_value = {"status": "unavailable", "error": "rabbit down"}
        mock_milvus.return_value = {"status": "unavailable", "error": "milvus down"}
        mock_minio.return_value = {"status": "unavailable", "error": "minio down"}

        response = client.get("/api/v1/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    for service in ("postgres", "redis", "rabbitmq", "milvus", "minio"):
        assert data["services"][service]["status"] == "unavailable"
