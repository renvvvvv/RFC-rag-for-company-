"""End-to-end tests for retrieval (search) and chat APIs.

This script exercises the full retrieval/chat surface:

- hybrid, semantic and keyword search
- search history
- non-streaming chat
- conversation CRUD and chat with history
- message feedback

It creates a low-security test user so the chat is not intercepted by the
local-only security strategy.
"""
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

BASE_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")
ADMIN_USER = os.environ.get("RAG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("RAG_ADMIN_PASS")
TEST_USER = os.environ.get("RAG_TEST_USER", "retrieval_test_user")
TEST_PASS = os.environ.get("RAG_TEST_PASS", "Test1234!")

if not ADMIN_PASS:
    print(
        "[ERROR] RAG_ADMIN_PASS environment variable is not set. "
        "Set it to the admin password before running this script."
    )
    sys.exit(1)


def login(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_test_user(admin_token: str) -> None:
    """Create the low-security test user if it does not exist."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/users",
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
    )
    if resp.status_code == 201:
        print(f"[OK] Created test user '{TEST_USER}' (L1)")
        return
    if resp.status_code == 400 and (
        "already exists" in resp.text.lower()
        or "已存在" in resp.text
        or "\u5df2\u5b58\u5728" in resp.text
    ):
        print(f"[OK] Test user '{TEST_USER}' already exists")
        return
    resp.raise_for_status()


def ensure_mock_llm_config(admin_token: str) -> None:
    """Point runtime LLM config at the local mock LLM service."""
    resp = requests.put(
        f"{BASE_URL}/api/v1/config/models",
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
    )
    resp.raise_for_status()
    print("[OK] Runtime LLM config points to mock llm-service")


def list_knowledge_bases(token: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        f"{BASE_URL}/api/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def pick_kb_with_indexed_docs(kbs: List[Dict[str, Any]], token: str) -> Optional[str]:
    """Return the first KB that contains indexed documents."""
    for kb in kbs:
        kb_id = kb["id"]
        resp = requests.get(
            f"{BASE_URL}/api/v1/documents/{kb_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        indexed = [d for d in items if d.get("status") == "indexed"]
        if indexed:
            print(f"[OK] Using KB '{kb.get('name')}' ({kb_id}) with {len(indexed)} indexed docs")
            return kb_id
    return None


def call_search(token: str, kb_id: str, mode: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/api/v1/search"
    if mode in ("semantic", "keyword"):
        url = f"{url}/{mode}"
    resp = requests.post(
        url,
        json={
            "query": "企业RAG",
            "kb_ids": [kb_id],
            "mode": mode,
            "top_k": 5,
            "rerank_top_k": 3,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    return resp.json()


def get_search_history(token: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        f"{BASE_URL}/api/v1/search/history?limit=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def chat(token: str, kb_id: str, query: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "kb_ids": [kb_id],
        "query": query,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    return resp.json()


def create_conversation(token: str, kb_id: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/conversations",
        json={"title": "检索测试会话", "kb_ids": [kb_id]},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def list_conversations(token: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        f"{BASE_URL}/api/v1/chat/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def get_messages(token: str, conversation_id: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        f"{BASE_URL}/api/v1/chat/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def submit_feedback(token: str, message_id: str) -> None:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/messages/{message_id}/feedback",
        json={"rating": 1, "comment": "测试反馈"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()


def assert_field(value: Any, name: str, expected_type: type) -> None:
    if value is None:
        raise AssertionError(f"{name} is None")
    if not isinstance(value, expected_type):
        raise AssertionError(f"{name} has wrong type: {type(value).__name__}")


def main() -> int:
    print("=" * 60)
    print("Retrieval & Chat API end-to-end tests")
    print(f"API: {BASE_URL}")
    print("=" * 60)

    admin_token = login(ADMIN_USER, ADMIN_PASS)
    print("[OK] Admin logged in")

    ensure_mock_llm_config(admin_token)
    create_test_user(admin_token)

    token = login(TEST_USER, TEST_PASS)
    print("[OK] Test user logged in")

    kbs = list_knowledge_bases(token)
    print(f"[INFO] Found {len(kbs)} knowledge bases")
    if not kbs:
        print("[ERROR] No knowledge bases found; run test_upload_to_kbs.py first")
        return 1

    kb_id = pick_kb_with_indexed_docs(kbs, token)
    if not kb_id:
        print("[ERROR] No knowledge base with indexed documents found")
        return 1

    failures = 0

    # ------------------------------------------------------------------
    # Search tests
    # ------------------------------------------------------------------
    print("\n--- Search tests ---")
    for mode in ("hybrid", "semantic", "keyword"):
        try:
            result = call_search(token, kb_id, mode)
            assert_field(result.get("query"), f"{mode}.query", str)
            assert_field(result.get("total"), f"{mode}.total", int)
            assert isinstance(result.get("results"), list)
            print(f"[OK] {mode:8} search returned total={result['total']}")
        except Exception as exc:
            print(f"[FAIL] {mode} search: {exc}")
            failures += 1

    try:
        history = get_search_history(token)
        print(f"[OK] Search history returned {len(history)} records")
    except Exception as exc:
        print(f"[FAIL] Search history: {exc}")
        failures += 1

    # ------------------------------------------------------------------
    # Chat tests
    # ------------------------------------------------------------------
    print("\n--- Chat tests ---")
    try:
        chat_result = chat(token, kb_id, "企业RAG是什么")
        assert_field(chat_result.get("answer"), "chat.answer", str)
        assert isinstance(chat_result.get("sources"), list)
        print(f"[OK] Non-streaming chat answered (intercepted={chat_result.get('intercepted')})")
    except Exception as exc:
        print(f"[FAIL] Non-streaming chat: {exc}")
        failures += 1

    try:
        conversation_id = create_conversation(token, kb_id)
        print(f"[OK] Created conversation {conversation_id}")
    except Exception as exc:
        print(f"[FAIL] Create conversation: {exc}")
        failures += 1
        conversation_id = None

    if conversation_id:
        try:
            conversations = list_conversations(token)
            ids = {c["id"] for c in conversations}
            if conversation_id not in ids:
                raise AssertionError("new conversation not in list")
            print(f"[OK] Listed {len(conversations)} conversations")
        except Exception as exc:
            print(f"[FAIL] List conversations: {exc}")
            failures += 1

        try:
            chat_with_history = chat(token, kb_id, "有哪些功能？", conversation_id=conversation_id)
            assert_field(chat_with_history.get("answer"), "chat_with_history.answer", str)
            print("[OK] Chat with history returned answer")
        except Exception as exc:
            print(f"[FAIL] Chat with history: {exc}")
            failures += 1

        try:
            messages = get_messages(token, conversation_id)
            assert len(messages) >= 2
            print(f"[OK] Conversation has {len(messages)} messages")
        except Exception as exc:
            print(f"[FAIL] Get messages: {exc}")
            failures += 1

        if messages:
            try:
                assistant_msg = [m for m in messages if m.get("role") == "assistant"][-1]
                submit_feedback(token, assistant_msg["id"])
                print("[OK] Submitted feedback")
            except Exception as exc:
                print(f"[FAIL] Feedback: {exc}")
                failures += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures == 0:
        print("All retrieval & chat tests passed")
        return 0
    print(f"{failures} test(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
