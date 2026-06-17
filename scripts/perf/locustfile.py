"""Locust load-test harness for the Enterprise Private RAG backend.

Targets the local FastAPI API at /api/v1 and exercises the endpoints most
likely to see production load:

- Health check (anonymous)
- Auth (login + /me)
- Knowledge base listing / stats
- Search (hybrid, semantic, keyword)
- Chat completion (non-streaming)
- Document upload

Run headless via:
    scripts/perf/.venv/Scripts/python -m locust -f scripts/perf/locustfile.py \
        --headless -u 50 -r 5 -t 60s --host http://localhost:8080

Or use the convenience wrappers:
    scripts/perf/run.sh
    scripts/perf/.venv/Scripts/python scripts/perf/run_load_test.py
"""
from __future__ import annotations

import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from locust import FastHttpUser, between, events, task

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
ADMIN_USER = os.environ.get("RAG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("RAG_ADMIN_PASS", "admin123")
TEST_USER = os.environ.get("RAG_TEST_USER", "loadtest_user")
TEST_PASS = os.environ.get("RAG_TEST_PASS", "Test1234!")
SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"
SMALL_UPLOAD = Path(__file__).resolve().parent / "loadtest_upload.md"

# Shared mutable state populated by the test_start event.
STATE: Dict[str, Any] = {
    "admin_token": None,
    "test_kb_id": None,
    "uploaded_doc_ids": [],
}

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _api_url(host: str, path: str) -> str:
    """Return a fully-qualified API URL."""
    base = host.rstrip("/")
    return f"{base}{path}"


def _login(base_url: str, username: str, password: str) -> str:
    """Login and return a bearer token."""
    resp = requests.post(
        _api_url(base_url, "/api/v1/auth/login"),
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _ensure_test_user(admin_token: str, base_url: str) -> None:
    """Create a low-security test user for chat/search if it does not exist."""
    resp = requests.post(
        _api_url(base_url, "/api/v1/users"),
        json={
            "username": TEST_USER,
            "email": f"{TEST_USER}@example.com",
            "password": TEST_PASS,
            "security_level": "L1",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if resp.status_code in (201, 400):
        return
    resp.raise_for_status()


def _ensure_mock_llm_config(admin_token: str, base_url: str) -> None:
    """Point runtime LLM config at the local mock service for repeatable chat."""
    resp = requests.put(
        _api_url(base_url, "/api/v1/config/models"),
        json={
            "llm_api_url": "http://llm-service:8080/v1/chat/completions",
            "llm_model": "mock-llm",
            "llm_api_key": "",
            "minimax_api_key": "",
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    # 404 means the config endpoint is not present; the stack may already be configured.
    if resp.status_code not in (200, 201, 404):
        resp.raise_for_status()


def _pick_kb_with_indexed_docs(admin_token: str, base_url: str) -> Optional[str]:
    """Return the first knowledge base that has at least one indexed document."""
    resp = requests.get(
        _api_url(base_url, "/api/v1/knowledge-bases"),
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    kbs = resp.json()
    for kb in kbs:
        kb_id = kb["id"]
        docs_resp = requests.get(
            _api_url(base_url, f"/api/v1/documents/{kb_id}"),
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        docs_resp.raise_for_status()
        items = docs_resp.json().get("items", [])
        indexed = [d for d in items if d.get("status") == "indexed"]
        if indexed:
            return kb_id
    return None


def _create_test_kb(admin_token: str, base_url: str) -> str:
    """Create a throw-away knowledge base for the load test."""
    resp = requests.post(
        _api_url(base_url, "/api/v1/knowledge-bases"),
        json={
            "name": f"LoadTestKB_{uuid.uuid4().hex[:6]}",
            "description": "Auto-created by Locust load test",
            "config": {},
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _upload_sample_doc(admin_token: str, base_url: str, kb_id: str, file_path: Path) -> str:
    """Upload a document and return its id."""
    with open(file_path, "rb") as f:
        resp = requests.post(
            _api_url(base_url, "/api/v1/documents"),
            data={"kb_id": kb_id},
            files={"file": (file_path.name, f, "text/markdown")},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["id"]


def _wait_for_indexed(doc_id: str, admin_token: str, base_url: str, timeout: int = 180) -> None:
    """Poll until the document reaches indexed status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            _api_url(base_url, f"/api/v1/documents/detail/{doc_id}"),
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json().get("status")
        if status == "indexed":
            return
        if status in ("failed", "error"):
            raise RuntimeError(f"Document {doc_id} indexing failed: {status}")
        time.sleep(5)
    raise TimeoutError(f"Document {doc_id} did not reach indexed within {timeout}s")


def _prepare_upload_file() -> Path:
    """Create a small deterministic markdown file for upload load testing."""
    if SMALL_UPLOAD.exists():
        return SMALL_UPLOAD
    SMALL_UPLOAD.write_text(
        "# Load Test Document\n\n"
        "This is a small sample document used by the Locust load test suite.\n\n"
        "- Enterprise RAG provides hybrid retrieval.\n"
        "- It supports semantic and keyword search.\n"
        "- Documents are parsed, chunked, embedded and indexed.\n",
        encoding="utf-8",
    )
    return SMALL_UPLOAD


# --------------------------------------------------------------------------- #
# Test lifecycle
# --------------------------------------------------------------------------- #
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """One-time setup: login, ensure test user / KB / indexed doc, configure LLM."""
    host = environment.host or "http://localhost:8080"
    try:
        admin_token = _login(host, ADMIN_USER, ADMIN_PASS)
        STATE["admin_token"] = admin_token

        _ensure_test_user(admin_token, host)
        _ensure_mock_llm_config(admin_token, host)

        kb_id = _pick_kb_with_indexed_docs(admin_token, host)
        if not kb_id:
            kb_id = _create_test_kb(admin_token, host)
            upload_file = _prepare_upload_file()
            doc_id = _upload_sample_doc(admin_token, host, kb_id, upload_file)
            _wait_for_indexed(doc_id, admin_token, host)
            STATE["uploaded_doc_ids"].append(doc_id)

        STATE["test_kb_id"] = kb_id
        environment.events.request.fire(
            request_type="SETUP",
            name="load_test_setup",
            response_time=0,
            response_length=0,
            response=None,
            context=None,
            exception=None,
        )
        print(f"[SETUP] Using KB {kb_id} for search/chat load tests")
    except Exception as exc:
        print(f"[SETUP ERROR] {exc}")
        environment.events.request.fire(
            request_type="SETUP",
            name="load_test_setup",
            response_time=0,
            response_length=0,
            response=None,
            context=None,
            exception=exc,
        )
        raise


# --------------------------------------------------------------------------- #
# User classes
# --------------------------------------------------------------------------- #
class HealthCheckUser(FastHttpUser):
    """Anonymous health-check traffic."""

    weight = 5
    wait_time = between(0.5, 1.5)

    @task
    def health(self):
        with self.client.get("/api/v1/health", catch_response=True, name="GET /health") as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") != "ok":
                    resp.failure(f"degraded health: {data}")
            else:
                resp.failure(f"unexpected status {resp.status_code}")


class AuthUser(FastHttpUser):
    """Authenticated user repeatedly logging in and fetching /me."""

    weight = 3
    wait_time = between(0.5, 2)

    def on_start(self):
        self.token = None
        self._do_login()

    def _do_login(self):
        with self.client.post(
            "/api/v1/auth/login",
            data={"username": ADMIN_USER, "password": ADMIN_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            catch_response=True,
            name="POST /auth/login",
        ) as resp:
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
            else:
                resp.failure(f"login failed: {resp.status_code}")

    @task(3)
    def login_and_me(self):
        self._do_login()
        if not self.token:
            return
        with self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="GET /auth/me",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"me failed: {resp.status_code}")

    @task(1)
    def me_only(self):
        if not self.token:
            self._do_login()
        if not self.token:
            return
        with self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="GET /auth/me",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"me failed: {resp.status_code}")


class KnowledgeBaseUser(FastHttpUser):
    """Authenticated user browsing knowledge bases."""

    weight = 5
    wait_time = between(0.5, 2)

    def on_start(self):
        self.token = self._login()

    def _login(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            data={"username": ADMIN_USER, "password": ADMIN_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /auth/login (kb)",
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @task(4)
    def list_kbs(self):
        self.client.get(
            "/api/v1/knowledge-bases",
            headers={"Authorization": f"Bearer {self.token}"},
            name="GET /knowledge-bases",
        )

    @task(2)
    def list_docs(self):
        kb_id = STATE.get("test_kb_id")
        if not kb_id:
            return
        self.client.get(
            f"/api/v1/documents/{kb_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            name="GET /documents/{kb_id}",
        )

    @task(1)
    def kb_stats(self):
        kb_id = STATE.get("test_kb_id")
        if not kb_id:
            return
        self.client.get(
            f"/api/v1/knowledge-bases/{kb_id}/stats",
            headers={"Authorization": f"Bearer {self.token}"},
            name="GET /knowledge-bases/{id}/stats",
        )


class SearchUser(FastHttpUser):
    """Authenticated user executing search requests against a real KB."""

    weight = 10
    wait_time = between(1, 3)

    QUERIES = ["企业RAG", "产品介绍", "技术白皮书", "财务数据", "项目计划", "客户服务"]

    def on_start(self):
        self.token = self._login()

    def _login(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            data={"username": ADMIN_USER, "password": ADMIN_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /auth/login (search)",
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _search(self, mode: str):
        kb_id = STATE.get("test_kb_id")
        if not kb_id:
            return
        query = random.choice(self.QUERIES)
        url = f"/api/v1/search/{mode}" if mode in ("semantic", "keyword") else "/api/v1/search"
        with self.client.post(
            url,
            json={
                "query": query,
                "kb_ids": [kb_id],
                "mode": mode,
                "top_k": 5,
                "rerank_top_k": 3,
            },
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            catch_response=True,
            name=f"POST /search/{mode}",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "results" not in data:
                    resp.failure("missing results field")
            else:
                resp.failure(f"search {mode} failed: {resp.status_code} {resp.text[:200]}")

    @task(5)
    def hybrid_search(self):
        self._search("hybrid")

    @task(2)
    def semantic_search(self):
        self._search("semantic")

    @task(2)
    def keyword_search(self):
        self._search("keyword")

    @task(1)
    def search_history(self):
        self.client.get(
            "/api/v1/search/history?limit=20",
            headers={"Authorization": f"Bearer {self.token}"},
            name="GET /search/history",
        )


class ChatUser(FastHttpUser):
    """Authenticated user sending non-streaming chat completion requests."""

    weight = 5
    wait_time = between(1, 3)

    QUERIES = [
        "什么是企业RAG？",
        "总结一下产品功能",
        "财务数据样例里有什么？",
        "项目计划包含哪些阶段？",
        "客户服务的常见问题有哪些？",
    ]

    def on_start(self):
        self.token = self._login()

    def _login(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            data={"username": TEST_USER, "password": TEST_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /auth/login (chat)",
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @task(1)
    def list_conversations(self):
        self.client.get(
            "/api/v1/chat/conversations",
            headers={"Authorization": f"Bearer {self.token}"},
            name="GET /chat/conversations",
        )

    @task(4)
    def chat(self):
        kb_id = STATE.get("test_kb_id")
        if not kb_id:
            return
        query = random.choice(self.QUERIES)
        with self.client.post(
            "/api/v1/chat",
            json={
                "kb_ids": [kb_id],
                "query": query,
                "top_k": 5,
                "rerank_top_k": 3,
                "stream": False,
            },
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            catch_response=True,
            name="POST /chat (non-stream)",
            timeout=60,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "answer" not in data:
                    resp.failure("missing answer field")
            else:
                resp.failure(f"chat failed: {resp.status_code} {resp.text[:200]}")


class DocumentUploadUser(FastHttpUser):
    """Authenticated user uploading a small sample document."""

    weight = 1
    wait_time = between(5, 10)

    def on_start(self):
        self.token = self._login()
        self.upload_file = _prepare_upload_file()

    def _login(self) -> str:
        resp = self.client.post(
            "/api/v1/auth/login",
            data={"username": ADMIN_USER, "password": ADMIN_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /auth/login (upload)",
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @task
    def upload_document(self):
        kb_id = STATE.get("test_kb_id")
        if not kb_id:
            return
        with open(self.upload_file, "rb") as f:
            with self.client.post(
                "/api/v1/documents",
                data={"kb_id": kb_id},
                files={"file": (self.upload_file.name, f, "text/markdown")},
                headers={"Authorization": f"Bearer {self.token}"},
                catch_response=True,
                name="POST /documents (upload)",
                timeout=60,
            ) as resp:
                if resp.status_code not in (200, 201):
                    resp.failure(f"upload failed: {resp.status_code} {resp.text[:200]}")
