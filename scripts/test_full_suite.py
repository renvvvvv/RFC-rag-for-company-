"""Full functional test suite for the Enterprise Private RAG backend.

Covers every documented API module end-to-end:
  Auth, Users, Knowledge Bases, Documents, Search, Chat, Permissions,
  Groups, Keywords, Evaluation, Config, Collaboration, Health.

Run prerequisites:
  - docker compose up -d

This script is self-contained: it creates a throw-away knowledge base,
uploads a sample document, waits for indexing, then exercises all modules.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

BASE_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")
ADMIN_USER = os.environ.get("RAG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("RAG_ADMIN_PASS")

if not ADMIN_PASS:
    print(
        "[ERROR] RAG_ADMIN_PASS environment variable is not set. "
        "Set it to the admin password before running this script."
    )
    sys.exit(1)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
INDEX_POLL_INTERVAL = 5
INDEX_POLL_TIMEOUT = 180


# --------------------------------------------------------------------------- #
# Test harness
# --------------------------------------------------------------------------- #
@dataclass
class TestContext:
    admin_token: str = ""
    tokens: Dict[str, str] = field(default_factory=dict)
    kb_id: str = ""
    doc_id: str = ""
    conversation_id: str = ""
    message_id: str = ""
    keyword_id: str = ""
    group_id: str = ""
    bookmark_id: str = ""
    comment_id: str = ""
    eval_dataset_id: str = ""
    eval_task_id: str = ""


class TestResult:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: List[str] = []

    def ok(self, name: str) -> None:
        print(f"  [OK] {name}")
        self.passed += 1

    def fail(self, name: str, exc: Exception) -> None:
        msg = f"  [FAIL] {name}: {exc}"
        print(msg)
        self.failed += 1
        self.failures.append(msg)


def login(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def ensure_mock_llm_config(admin_token: str) -> None:
    resp = requests.put(
        f"{BASE_URL}/api/v1/config/models",
        json={
            "llm_api_url": "http://llm-service:8080/v1/chat/completions",
            "llm_model": "mock-llm",
            "llm_api_key": "",
            "minimax_api_key": "",
        },
        headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
    )
    resp.raise_for_status()


def create_test_kb(token: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/knowledge-bases",
        json={"name": f"FullSuiteKB_{uuid.uuid4().hex[:6]}", "description": "Auto-created by full suite"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def upload_sample_doc(kb_id: str, token: str, filename: str = "01-企业RAG产品介绍.md") -> str:
    sample = SAMPLES_DIR / filename
    if not sample.exists():
        raise FileNotFoundError(f"Sample not found: {sample}")
    with open(sample, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents",
            data={"kb_id": kb_id},
            files={"file": (sample.name, f, "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
    resp.raise_for_status()
    return resp.json()["id"]


def wait_for_indexed(doc_id: str, token: str) -> None:
    deadline = time.time() + INDEX_POLL_TIMEOUT
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/detail/{doc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        status = resp.json().get("status")
        if status == "indexed":
            return
        if status in ("failed", "error"):
            raise RuntimeError(f"Document {doc_id} indexing failed with status '{status}'")
        print(f"    ... indexing status={status}, waiting {INDEX_POLL_INTERVAL}s")
        time.sleep(INDEX_POLL_INTERVAL)
    raise TimeoutError(f"Document {doc_id} did not reach 'indexed' within {INDEX_POLL_TIMEOUT}s")


def run_case(result: TestResult, name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
        result.ok(name)
    except Exception as exc:
        detail = ""
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            try:
                detail = f" | response={exc.response.status_code}: {exc.response.text[:500]}"
            except Exception:
                pass
        wrapped = Exception(f"{exc!r}{detail}")
        result.fail(name, wrapped)


# --------------------------------------------------------------------------- #
# Module tests
# --------------------------------------------------------------------------- #
def test_health(ctx: TestContext, result: TestResult) -> None:
    def case() -> None:
        resp = requests.get(f"{BASE_URL}/api/v1/health")
        resp.raise_for_status()
        data = resp.json()
        assert data["status"] == "ok"
        for svc in ("postgres", "redis", "rabbitmq", "milvus", "minio"):
            assert data["services"][svc]["status"] == "ok", f"{svc} not healthy"

    run_case(result, "Health check all services", case)


def test_auth(ctx: TestContext, result: TestResult) -> None:
    def register() -> None:
        uid = uuid.uuid4().hex[:8]
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={
                "username": f"register_test_{uid}",
                "email": f"register_test_{uid}@example.com",
                "password": "Test1234!",
                "security_level": "L1",
            },
        )
        resp.raise_for_status()
        assert resp.json()["username"] == f"register_test_{uid}"

    def me() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert resp.json()["username"] == "admin"

    run_case(result, "Auth register", register)
    run_case(result, "Auth me", me)


def test_users(ctx: TestContext, result: TestResult) -> None:
    user_id: Optional[str] = None

    def create() -> None:
        nonlocal user_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/users",
            json={
                "username": f"user_{uuid.uuid4().hex[:8]}",
                "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
                "password": "Test1234!",
                "security_level": "L2",
            },
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        user_id = resp.json()["id"]

    def list_users() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/users",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def get_user() -> None:
        assert user_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert resp.json()["id"] == user_id

    def update_user() -> None:
        assert user_id
        resp = requests.put(
            f"{BASE_URL}/api/v1/users/{user_id}",
            json={"security_level": "L3"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        assert resp.json()["security_level"] == "L3"

    def delete_user() -> None:
        assert user_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Users create", create)
    run_case(result, "Users list", list_users)
    run_case(result, "Users get", get_user)
    run_case(result, "Users update", update_user)
    run_case(result, "Users delete", delete_user)


def test_knowledge_bases(ctx: TestContext, result: TestResult) -> None:
    kb_id: Optional[str] = None

    def create() -> None:
        nonlocal kb_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/knowledge-bases",
            json={"name": f"Test KB {uuid.uuid4().hex[:6]}", "description": "Auto-created by full suite"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        kb_id = resp.json()["id"]

    def list_kbs() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/knowledge-bases",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def get_kb() -> None:
        assert kb_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/knowledge-bases/{kb_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert resp.json()["id"] == kb_id

    def update_kb() -> None:
        assert kb_id
        resp = requests.patch(
            f"{BASE_URL}/api/v1/knowledge-bases/{kb_id}",
            json={"description": "Updated description"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        assert resp.json()["description"] == "Updated description"

    def stats_kb() -> None:
        assert kb_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/knowledge-bases/{kb_id}/stats",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        assert "document_count" in data
        assert "chunk_count" in data
        assert "status_breakdown" in data

    def delete_kb() -> None:
        assert kb_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/knowledge-bases/{kb_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "KB create", create)
    run_case(result, "KB list", list_kbs)
    run_case(result, "KB get", get_kb)
    run_case(result, "KB update", update_kb)
    run_case(result, "KB stats", stats_kb)
    run_case(result, "KB delete", delete_kb)


def test_documents(ctx: TestContext, result: TestResult) -> None:
    doc_id: Optional[str] = None

    def create_kb() -> None:
        if ctx.kb_id:
            return
        resp = requests.post(
            f"{BASE_URL}/api/v1/knowledge-bases",
            json={"name": "DocTest KB", "description": "For document tests"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        ctx.kb_id = resp.json()["id"]

    def upload() -> None:
        nonlocal doc_id
        create_kb()
        sample = SAMPLES_DIR / "01-企业RAG产品介绍.md"
        if not sample.exists():
            raise FileNotFoundError(f"Sample not found: {sample}")
        with open(sample, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/v1/documents",
                data={"kb_id": ctx.kb_id},
                files={"file": (sample.name, f, "text/markdown")},
                headers={"Authorization": f"Bearer {ctx.admin_token}"},
            )
        resp.raise_for_status()
        doc_id = resp.json()["id"]

    def list_docs() -> None:
        assert ctx.kb_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/{ctx.kb_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json().get("items"), list)

    def get_doc() -> None:
        assert doc_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/detail/{doc_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert resp.json()["id"] == doc_id

    def reprocess_doc() -> None:
        assert doc_id
        # Reprocess only makes sense on an already-indexed document.
        wait_for_indexed(doc_id, ctx.admin_token)
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents/{doc_id}/reprocess",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        assert resp.status_code in (200, 202), f"unexpected status {resp.status_code}: {resp.text[:500]}"

    def delete_doc() -> None:
        assert doc_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/documents/detail/{doc_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Documents upload", upload)
    run_case(result, "Documents list", list_docs)
    run_case(result, "Documents get detail", get_doc)
    run_case(result, "Documents reprocess", reprocess_doc)
    run_case(result, "Documents delete", delete_doc)


def test_search(ctx: TestContext, result: TestResult) -> None:
    if not ctx.kb_id:
        result.fail("Search requires indexed KB", Exception("No KB available"))
        return

    def hybrid() -> None:
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "企业RAG", "kb_ids": [ctx.kb_id], "mode": "hybrid", "top_k": 5, "rerank_top_k": 3},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        assert "results" in resp.json()

    def semantic() -> None:
        resp = requests.post(
            f"{BASE_URL}/api/v1/search/semantic",
            json={"query": "企业RAG", "kb_ids": [ctx.kb_id], "top_k": 5, "rerank_top_k": 3},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def keyword() -> None:
        resp = requests.post(
            f"{BASE_URL}/api/v1/search/keyword",
            json={"query": "企业RAG", "kb_ids": [ctx.kb_id], "top_k": 5, "rerank_top_k": 3},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def history() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/search/history?limit=10",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert "items" in resp.json()

    run_case(result, "Search hybrid", hybrid)
    run_case(result, "Search semantic", semantic)
    run_case(result, "Search keyword", keyword)
    run_case(result, "Search history", history)


def test_chat(ctx: TestContext, result: TestResult) -> None:
    if not ctx.kb_id:
        result.fail("Chat requires indexed KB", Exception("No KB available"))
        return

    conv_id: Optional[str] = None
    msg_id: Optional[str] = None

    def chat_direct() -> None:
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={"kb_ids": [ctx.kb_id], "query": "你好"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        assert "answer" in data
        assert data.get("intercepted") is False

    def create_conversation() -> None:
        nonlocal conv_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/conversations",
            json={"title": "Full-suite conversation", "kb_ids": [ctx.kb_id]},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        conv_id = resp.json()["id"]

    def list_conversations() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/chat/conversations",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def chat_with_history() -> None:
        nonlocal msg_id
        assert conv_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={"kb_ids": [ctx.kb_id], "query": "有哪些功能", "conversation_id": conv_id},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        msg_id = _last_assistant_message_id(conv_id, ctx.admin_token)

    def get_messages() -> None:
        assert conv_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/chat/conversations/{conv_id}/messages",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert len(resp.json()) >= 2

    def feedback() -> None:
        assert msg_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/messages/{msg_id}/feedback",
            json={"rating": 1, "comment": "full-suite test"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def delete_conversation() -> None:
        assert conv_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Chat direct", chat_direct)
    run_case(result, "Chat create conversation", create_conversation)
    run_case(result, "Chat list conversations", list_conversations)
    run_case(result, "Chat with history", chat_with_history)
    run_case(result, "Chat get messages", get_messages)
    run_case(result, "Chat feedback", feedback)
    run_case(result, "Chat delete conversation", delete_conversation)


def _last_assistant_message_id(conv_id: str, token: str) -> str:
    resp = requests.get(
        f"{BASE_URL}/api/v1/chat/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    msgs = [m for m in resp.json() if m.get("role") == "assistant"]
    assert msgs
    return msgs[-1]["id"]


def test_permissions(ctx: TestContext, result: TestResult) -> None:
    if not ctx.doc_id:
        result.fail("Permission tests require a doc_id", Exception("No doc available"))
        return

    target_user: Optional[str] = None

    def setup_user() -> None:
        nonlocal target_user
        resp = requests.post(
            f"{BASE_URL}/api/v1/users",
            json={
                "username": f"perm_target_{uuid.uuid4().hex[:8]}",
                "email": f"perm_{uuid.uuid4().hex[:8]}@example.com",
                "password": "Test1234!",
                "security_level": "L1",
            },
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        target_user = resp.json()["id"]

    def doc_permission() -> None:
        assert target_user
        resp = requests.post(
            f"{BASE_URL}/api/v1/permissions/document",
            json={"target_type": "user", "target_id": target_user, "doc_id": ctx.doc_id, "permission": "read"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def file_type_permission() -> None:
        assert target_user
        resp = requests.post(
            f"{BASE_URL}/api/v1/permissions/file-type",
            json={"target_type": "user", "target_id": target_user, "file_type": "pdf", "permissions": ["read"]},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def check_permission() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/permissions/check/{ctx.doc_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    def list_permissions() -> None:
        assert target_user
        resp = requests.get(
            f"{BASE_URL}/api/v1/permissions/list?target_type=user&target_id={target_user}&object_type=document",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    def grant_and_revoke() -> None:
        assert target_user
        resp = requests.post(
            f"{BASE_URL}/api/v1/permissions/grant",
            json={
                "target_type": "user",
                "target_id": target_user,
                "object_type": "document",
                "object_id": ctx.doc_id,
                "permission": "write",
            },
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        resp = requests.post(
            f"{BASE_URL}/api/v1/permissions/revoke",
            json={
                "target_type": "user",
                "target_id": target_user,
                "object_type": "document",
                "object_id": ctx.doc_id,
                "permission": "write",
            },
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    run_case(result, "Permissions setup user", setup_user)
    run_case(result, "Permissions document", doc_permission)
    run_case(result, "Permissions file-type", file_type_permission)
    run_case(result, "Permissions check", check_permission)
    run_case(result, "Permissions list", list_permissions)
    run_case(result, "Permissions grant/revoke", grant_and_revoke)


def test_groups(ctx: TestContext, result: TestResult) -> None:
    group_id: Optional[str] = None
    member_id: Optional[str] = None

    def create_group() -> None:
        nonlocal group_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/groups",
            json={"name": f"TestGroup_{uuid.uuid4().hex[:6]}", "description": "Full suite group", "group_type": "department"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        group_id = resp.json()["id"]

    def list_groups() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/groups",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def add_member() -> None:
        nonlocal member_id
        assert group_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/users",
            json={
                "username": f"group_member_{uuid.uuid4().hex[:8]}",
                "email": f"gm_{uuid.uuid4().hex[:8]}@example.com",
                "password": "Test1234!",
                "security_level": "L1",
            },
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        member_id = resp.json()["id"]
        resp = requests.post(
            f"{BASE_URL}/api/v1/groups/{group_id}/members",
            json={"user_ids": [member_id]},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def remove_member() -> None:
        assert group_id and member_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/groups/{group_id}/members",
            json={"user_ids": [member_id]},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    def delete_group() -> None:
        assert group_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/groups/{group_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Groups create", create_group)
    run_case(result, "Groups list", list_groups)
    run_case(result, "Groups add member", add_member)
    run_case(result, "Groups remove member", remove_member)
    run_case(result, "Groups delete", delete_group)


def test_keywords(ctx: TestContext, result: TestResult) -> None:
    keyword_id: Optional[str] = None

    def create() -> None:
        nonlocal keyword_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/keywords",
            json={"keyword": "测试敏感词", "level": "L2", "category": "test", "match_type": "exact"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        keyword_id = resp.json()["id"]

    def list_keywords() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/keywords",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def scan() -> None:
        resp = requests.post(
            f"{BASE_URL}/api/v1/keywords/scan",
            json={"text": "这句话包含测试敏感词，需要检测。"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        assert "findings" in resp.json() or "matches" in resp.json()

    def update() -> None:
        assert keyword_id
        resp = requests.put(
            f"{BASE_URL}/api/v1/keywords/{keyword_id}",
            json={"level": "L3"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        assert resp.json()["level"] == "L3"

    def delete() -> None:
        assert keyword_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/keywords/{keyword_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Keywords create", create)
    run_case(result, "Keywords list", list_keywords)
    run_case(result, "Keywords scan", scan)
    run_case(result, "Keywords update", update)
    run_case(result, "Keywords delete", delete)


def test_evaluation(ctx: TestContext, result: TestResult) -> None:
    if not ctx.kb_id:
        result.fail("Eval requires indexed KB", Exception("No KB available"))
        return

    dataset_id: Optional[str] = None
    task_id: Optional[str] = None

    def create_dataset() -> None:
        nonlocal dataset_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/evaluation/datasets",
            json={
                "kb_id": ctx.kb_id,
                "name": f"FullSuiteDataset_{uuid.uuid4().hex[:6]}",
                "questions": ["企业RAG是什么？"],
                "ground_truths": [{"answer": "企业RAG是一种检索增强生成系统。"}],
            },
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        dataset_id = resp.json()["id"]

    def list_datasets() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/evaluation/datasets",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def create_task() -> None:
        nonlocal task_id
        assert dataset_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/evaluation/tasks",
            json={"dataset_id": dataset_id, "kb_id": ctx.kb_id, "metrics": ["recall@3"]},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        task_id = resp.json()["id"]

    def get_metrics() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/evaluation/metrics",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert "metrics" in resp.json()

    def get_task() -> None:
        assert task_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/evaluation/tasks/{task_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Eval create dataset", create_dataset)
    run_case(result, "Eval list datasets", list_datasets)
    run_case(result, "Eval create task", create_task)
    run_case(result, "Eval get metrics", get_metrics)
    run_case(result, "Eval get task", get_task)


def test_config(ctx: TestContext, result: TestResult) -> None:
    def get_config() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/config/models",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        assert "llm_api_url" in data

    def update_config() -> None:
        resp = requests.put(
            f"{BASE_URL}/api/v1/config/models",
            json={"llm_model": "mock-llm"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    run_case(result, "Config get models", get_config)
    run_case(result, "Config update models", update_config)


def test_collaboration(ctx: TestContext, result: TestResult) -> None:
    if not ctx.kb_id:
        result.fail("Collaboration tests require a KB", Exception("No KB available"))
        return

    comment_id: Optional[str] = None
    bookmark_id: Optional[str] = None

    def create_comment() -> None:
        nonlocal comment_id
        assert ctx.doc_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/comments",
            json={"target_type": "document", "target_id": ctx.doc_id, "content": "Full suite comment"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        comment_id = resp.json()["id"]

    def list_comments() -> None:
        assert ctx.doc_id
        resp = requests.get(
            f"{BASE_URL}/api/v1/comments?target_type=document&target_id={ctx.doc_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def delete_comment() -> None:
        assert comment_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/comments/{comment_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    def create_bookmark() -> None:
        nonlocal bookmark_id
        assert ctx.doc_id
        resp = requests.post(
            f"{BASE_URL}/api/v1/bookmarks",
            json={"target_type": "document", "target_id": ctx.doc_id, "note": "Full suite bookmark"},
            headers={"Authorization": f"Bearer {ctx.admin_token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        bookmark_id = resp.json()["id"]

    def list_bookmarks() -> None:
        resp = requests.get(
            f"{BASE_URL}/api/v1/bookmarks",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()
        assert isinstance(resp.json(), list)

    def delete_bookmark() -> None:
        assert bookmark_id
        resp = requests.delete(
            f"{BASE_URL}/api/v1/bookmarks/{bookmark_id}",
            headers={"Authorization": f"Bearer {ctx.admin_token}"},
        )
        resp.raise_for_status()

    run_case(result, "Collaboration create comment", create_comment)
    run_case(result, "Collaboration list comments", list_comments)
    run_case(result, "Collaboration delete comment", delete_comment)
    run_case(result, "Collaboration create bookmark", create_bookmark)
    run_case(result, "Collaboration list bookmarks", list_bookmarks)
    run_case(result, "Collaboration delete bookmark", delete_bookmark)


# --------------------------------------------------------------------------- #
# Main orchestration
# --------------------------------------------------------------------------- #
def main() -> int:
    print("=" * 70)
    print("Enterprise Private RAG — Full Functional Test Suite")
    print(f"API: {BASE_URL}")
    print("=" * 70)

    ctx = TestContext()
    result = TestResult()

    # Global setup
    try:
        ctx.admin_token = login(ADMIN_USER, ADMIN_PASS)
        print("[OK] Admin logged in")
        ensure_mock_llm_config(ctx.admin_token)
        print("[OK] Mock LLM config ensured")

        ctx.kb_id = create_test_kb(ctx.admin_token)
        print(f"[OK] Test KB created: {ctx.kb_id}")

        ctx.doc_id = upload_sample_doc(ctx.kb_id, ctx.admin_token)
        print(f"[OK] Sample document uploaded: {ctx.doc_id}")

        print("[INFO] Waiting for document indexing...")
        wait_for_indexed(ctx.doc_id, ctx.admin_token)
        print("[OK] Sample document indexed")
    except Exception as exc:
        print(f"[FATAL] Global setup failed: {exc}")
        return 1

    modules = [
        ("Health", test_health),
        ("Auth", test_auth),
        ("Users", test_users),
        ("Knowledge Bases", test_knowledge_bases),
        ("Documents", test_documents),
        ("Search", test_search),
        ("Chat", test_chat),
        ("Permissions", test_permissions),
        ("Groups", test_groups),
        ("Keywords", test_keywords),
        ("Evaluation", test_evaluation),
        ("Config", test_config),
        ("Collaboration", test_collaboration),
    ]

    for name, fn in modules:
        print(f"\n--- {name} ---")
        fn(ctx, result)

    print("\n" + "=" * 70)
    print(f"Passed: {result.passed}")
    print(f"Failed: {result.failed}")
    if result.failures:
        print("\nFailures:")
        for f in result.failures:
            print(f)
    print("=" * 70)
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
