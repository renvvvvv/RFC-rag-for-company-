"""Check document indexing status for recently uploaded files."""
import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

ADMIN_USER = os.environ.get("RAG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("RAG_ADMIN_PASS")

if not ADMIN_PASS:
    print(
        "[ERROR] RAG_ADMIN_PASS environment variable is not set. "
        "Set it to the admin password before running this script."
    )
    sys.exit(1)


def list_docs(token: str, kb_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/api/v1/documents/{kb_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def list_kbs(token: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/api/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def login() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else None
    if not token:
        print("No token provided, logging in as admin...")
        token = login()

    print("Fetching knowledge bases...")
    kbs = list_kbs(token)
    print(f"Found {len(kbs)} knowledge bases\n")

    for kb in kbs:
        kb_id = kb["id"]
        kb_name = kb["name"]
        docs = list_docs(token, kb_id)
        if not docs:
            continue
        print(f"=== {kb_name} ({kb_id}) ===")
        for doc in docs:
            status = doc.get("status", "unknown")
            filename = doc.get("filename") or doc.get("title", "N/A")
            file_type = doc.get("file_type", "N/A")
            print(f"  [{status:12}] {filename} ({file_type})")
        print()


if __name__ == "__main__":
    main()
