"""Test uploading sample files to multiple knowledge bases via backend API."""
import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

# Admin credentials MUST be provided via environment variables.
USERNAME = os.environ.get("RAG_ADMIN_USER", "admin")
PASSWORD = os.environ.get("RAG_ADMIN_PASS")

if not PASSWORD:
    print(
        "[ERROR] RAG_ADMIN_PASS environment variable is not set. "
        "Set it to the admin password before running this script."
    )
    sys.exit(1)


def login() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"[OK] Logged in as {USERNAME}")
    return token


def create_kb(token: str, name: str, description: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/knowledge-bases",
        json={"name": name, "description": description},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    kb_id = resp.json()["id"]
    print(f"[OK] Created KB '{name}': {kb_id}")
    return kb_id


def upload_file(token: str, kb_id: str, file_path: Path) -> dict:
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents",
            data={"kb_id": kb_id, "title": file_path.name},
            files={"file": (file_path.name, f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
    resp.raise_for_status()
    result = resp.json()
    print(f"[OK] Uploaded {file_path.name} -> doc_id={result.get('id', result.get('document_id', 'N/A'))}")
    return result


def list_docs(token: str, kb_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/api/v1/documents/{kb_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def wait_for_indexing(token: str, kb_id: str, timeout: int = 120) -> bool:
    print(f"[INFO] Waiting for documents in KB {kb_id} to be processed (timeout {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = list_docs(token, kb_id)
        if not docs:
            time.sleep(2)
            continue
        pending = [d for d in docs if d.get("status") in ("pending", "processing")]
        if not pending:
            print(f"[OK] All {len(docs)} documents processed")
            return True
        statuses = [f"{d.get('filename', d.get('title', 'doc'))}:{d.get('status')}" for d in docs]
        print(f"[INFO] Statuses: {', '.join(statuses)}")
        time.sleep(5)
    print("[WARN] Timeout waiting for document processing")
    return False


def main():
    if not SAMPLES_DIR.exists():
        print(f"[ERROR] Samples directory not found: {SAMPLES_DIR}")
        print("Run: python scripts/generate_sample_files.py")
        sys.exit(1)

    token = login()

    test_cases = [
        {
            "name": "产品文档库",
            "description": "存放产品介绍、白皮书、FAQ 等文档",
            "files": [
                "01-企业RAG产品介绍.md",
                "03-产品功能说明.pdf",
                "05-技术白皮书.docx",
                "07-客户服务FAQ.md",
            ],
        },
        {
            "name": "财务数据库",
            "description": "存放财务报表和预算数据",
            "files": [
                "04-财务数据样例.xlsx",
            ],
        },
        {
            "name": "项目资料库",
            "description": "存放项目计划、组织架构等项目资料",
            "files": [
                "02-企业RAG产品介绍.txt",
                "06-组织架构图.png",
                "08-项目计划表.xlsx",
            ],
        },
    ]

    summary = []
    for case in test_cases:
        print(f"\n=== KB: {case['name']} ===")
        try:
            kb_id = create_kb(token, case["name"], case["description"])
        except requests.HTTPError as e:
            print(f"[ERROR] Failed to create KB: {e.response.text}")
            summary.append({"kb": case["name"], "status": "failed", "error": f"create_kb: {e.response.text}"})
            continue

        uploaded = []
        failed = []
        for filename in case["files"]:
            file_path = SAMPLES_DIR / filename
            if not file_path.exists():
                print(f"[WARN] File not found: {file_path}")
                failed.append(filename)
                continue
            try:
                upload_file(token, kb_id, file_path)
                uploaded.append(filename)
            except requests.HTTPError as e:
                print(f"[ERROR] Failed to upload {filename}: {e.response.text}")
                failed.append(filename)

        indexed = wait_for_indexing(token, kb_id) if uploaded else False
        summary.append({
            "kb": case["name"],
            "kb_id": kb_id,
            "status": "ok" if not failed and uploaded and indexed else "partial" if uploaded else "failed",
            "uploaded": uploaded,
            "failed": failed,
            "indexed": indexed,
        })

    print("\n=== SUMMARY ===")
    for item in summary:
        print(f"KB: {item['kb']}")
        print(f"  ID: {item.get('kb_id', 'N/A')}")
        print(f"  Status: {item['status']}")
        print(f"  Uploaded ({len(item['uploaded'])}): {', '.join(item['uploaded'])}")
        if item['failed']:
            print(f"  Failed ({len(item['failed'])}): {', '.join(item['failed'])}")
        print(f"  Indexed: {'Yes' if item.get('indexed') else 'No/Timeout'}")

    all_ok = all(item["status"] == "ok" for item in summary)

    print("\n[INFO] Upload test finished. To check indexing status, run:")
    print(f"  python scripts/check_doc_status.py {token}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
