"""Retrieval-quality evaluation script for the Enterprise Private RAG backend.

This script establishes a reproducible baseline for retrieval quality by:

1. Creating (or reusing) a dedicated evaluation knowledge base.
2. Uploading a small, annotated set of sample documents.
3. Waiting for document indexing to complete.
4. Running annotated queries against the three search modes (hybrid, semantic, keyword).
5. Computing recall@k, precision@k, MRR and nDCG@k.
6. Printing per-query results and aggregate metrics.

The current backend uses a mock embedding service that returns zero vectors,
so semantic and hybrid vector search are expected to underperform. Keyword
search (PostgreSQL full-text search on content_tsv) should still return
relevant results. This baseline is intentionally captured as-is so future
improvements (real embedding model, reranker, hybrid tuning) can be measured.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_ROOT / "samples"

BASE_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")
ADMIN_USER = os.environ.get("RAG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("RAG_ADMIN_PASS", "admin123")

EVAL_KB_NAME = "retrieval-eval-kb"
EVAL_KB_DESC = "Dedicated knowledge base for retrieval quality evaluation"

# Documents to use for the evaluation corpus. All files must exist under samples/.
SAMPLE_FILES = [
    "01-企业RAG产品介绍.md",
    "02-企业RAG产品介绍.txt",
    "03-产品功能说明.pdf",
    "04-财务数据样例.xlsx",
    "05-技术白皮书.docx",
    "07-客户服务FAQ.md",
    "08-项目计划表.xlsx",
]

# Annotated queries. Each entry maps a natural-language query to the set of
# sample filenames that are considered relevant for that query.
# Filenames are translated to backend doc_ids after upload.
#
# NOTE: The current PostgreSQL full-text search uses the "simple" text-search
# configuration, which does NOT segment Chinese phrases. Therefore keyword
# search works best with English/Latin tokens that appear in the content
# (RAG, BM25, Docker Compose, Kong, API, 2025, Q1, Faithfulness, etc.).
# Chinese-only queries are intentionally included below as a regression test
# so the baseline clearly exposes this limitation.
QUERY_ANNOTATIONS: List[Dict[str, Any]] = [
    {
        "query": "RAG",
        "expected_files": [
            "01-企业RAG产品介绍.md",
            "02-企业RAG产品介绍.txt",
            "03-产品功能说明.pdf",
            "05-技术白皮书.docx",
            "08-项目计划表.xlsx",
        ],
    },
    {
        "query": "BM25",
        "expected_files": [
            "01-企业RAG产品介绍.md",
            "02-企业RAG产品介绍.txt",
            "05-技术白皮书.docx",
        ],
    },
    {
        "query": "Docker Compose",
        "expected_files": [
            "01-企业RAG产品介绍.md",
            "02-企业RAG产品介绍.txt",
            "05-技术白皮书.docx",
        ],
    },
    {
        "query": "Kong API JWT",
        "expected_files": ["07-客户服务FAQ.md"],
    },
    {
        "query": "PDF Word Excel",
        "expected_files": ["07-客户服务FAQ.md"],
    },
    {
        "query": "Prometheus",
        "expected_files": ["03-产品功能说明.pdf"],
    },
    {
        "query": "2025年度财务概览",
        "expected_files": ["04-财务数据样例.xlsx"],
    },
    {
        "query": "RAG项目里程碑",
        "expected_files": ["08-项目计划表.xlsx"],
    },
    {
        "query": "系统支持哪些文件格式",
        "expected_files": ["07-客户服务FAQ.md"],
    },
    {
        "query": "私有化部署",
        "expected_files": [
            "01-企业RAG产品介绍.md",
            "02-企业RAG产品介绍.txt",
            "05-技术白皮书.docx",
        ],
    },
]

K_VALUES = [1, 3, 5, 10]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def login(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"[OK] Logged in as {username}")
    return token


def ensure_eval_kb(token: str) -> str:
    """Create the evaluation KB if it does not exist; otherwise reuse it."""
    resp = requests.get(
        f"{BASE_URL}/api/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    for kb in resp.json():
        if kb.get("name") == EVAL_KB_NAME:
            print(f"[OK] Reusing evaluation KB '{EVAL_KB_NAME}': {kb['id']}")
            return kb["id"]

    resp = requests.post(
        f"{BASE_URL}/api/v1/knowledge-bases",
        json={"name": EVAL_KB_NAME, "description": EVAL_KB_DESC, "config": {}},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    kb_id = resp.json()["id"]
    print(f"[OK] Created evaluation KB '{EVAL_KB_NAME}': {kb_id}")
    return kb_id


def upload_file(token: str, kb_id: str, file_path: Path) -> Dict[str, Any]:
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/v1/documents",
            data={"kb_id": kb_id, "title": file_path.name},
            files={"file": (file_path.name, f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
    resp.raise_for_status()
    return resp.json()


def list_docs(token: str, kb_id: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        f"{BASE_URL}/api/v1/documents/{kb_id}?limit=100",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def wait_for_indexing(token: str, kb_id: str, timeout: int = 180) -> bool:
    print(f"[INFO] Waiting for documents in KB {kb_id} to be indexed (timeout {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = list_docs(token, kb_id)
        if not docs:
            time.sleep(2)
            continue
        pending = [d for d in docs if d.get("status") in ("pending", "processing")]
        if not pending:
            indexed = [d for d in docs if d.get("status") == "indexed"]
            print(f"[OK] All {len(docs)} documents processed ({len(indexed)} indexed)")
            return True
        statuses = [f"{d.get('filename', 'doc')}:{d.get('status')}" for d in docs]
        print(f"[INFO] Statuses: {', '.join(statuses)}")
        time.sleep(5)
    print("[WARN] Timeout waiting for document processing")
    return False


def search(token: str, kb_id: str, query: str, mode: str, top_k: int, rerank_top_k: int) -> Dict[str, Any]:
    url = f"{BASE_URL}/api/v1/search"
    if mode in ("semantic", "keyword"):
        url = f"{url}/{mode}"
    resp = requests.post(
        url,
        json={
            "query": query,
            "kb_ids": [kb_id],
            "mode": mode,
            "top_k": top_k,
            "rerank_top_k": rerank_top_k,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def recall_at_k(retrieved_doc_ids: Sequence[str], relevant_doc_ids: Set[str], k: int) -> float:
    if not relevant_doc_ids:
        return 0.0
    retrieved_k = retrieved_doc_ids[:k]
    relevant_retrieved = len(set(retrieved_k) & relevant_doc_ids)
    return relevant_retrieved / len(relevant_doc_ids)


def precision_at_k(retrieved_doc_ids: Sequence[str], relevant_doc_ids: Set[str], k: int) -> float:
    if k == 0:
        return 0.0
    retrieved_k = retrieved_doc_ids[:k]
    relevant_retrieved = len(set(retrieved_k) & relevant_doc_ids)
    return relevant_retrieved / k


def mrr(retrieved_doc_ids: Sequence[str], relevant_doc_ids: Set[str]) -> float:
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in relevant_doc_ids:
            return 1.0 / rank
    return 0.0


def dcg_at_k(relevances: Sequence[int], k: int) -> float:
    return sum(
        rel / math.log2(idx + 2) for idx, rel in enumerate(relevances[:k])
    )


def ndcg_at_k(retrieved_doc_ids: Sequence[str], relevant_doc_ids: Set[str], k: int) -> float:
    relevances = [1 if doc_id in relevant_doc_ids else 0 for doc_id in retrieved_doc_ids]
    ideal_relevances = sorted(relevances, reverse=True)
    dcg = dcg_at_k(relevances, k)
    idcg = dcg_at_k(ideal_relevances, k)
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Evaluation orchestration
# ---------------------------------------------------------------------------


def build_filename_to_doc_id(docs: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for doc in docs:
        filename = doc.get("filename") or doc.get("title")
        doc_id = doc.get("id")
        if filename and doc_id:
            mapping[filename] = str(doc_id)
    return mapping


def evaluate_query(
    token: str,
    kb_id: str,
    query: str,
    relevant_doc_ids: Set[str],
    modes: Sequence[str],
    top_k: int,
    rerank_top_k: int,
) -> Dict[str, Any]:
    per_mode: Dict[str, Any] = {}
    for mode in modes:
        response = search(token, kb_id, query, mode, top_k, rerank_top_k)
        retrieved_doc_ids = [r.get("doc_id") for r in response.get("results", []) if r.get("doc_id")]

        per_mode[mode] = {
            "total": response.get("total", 0),
            "retrieved_doc_ids": retrieved_doc_ids,
            "recall@k": {k: recall_at_k(retrieved_doc_ids, relevant_doc_ids, k) for k in K_VALUES},
            "precision@k": {k: precision_at_k(retrieved_doc_ids, relevant_doc_ids, k) for k in K_VALUES},
            "mrr": mrr(retrieved_doc_ids, relevant_doc_ids),
            "ndcg@k": {k: ndcg_at_k(retrieved_doc_ids, relevant_doc_ids, k) for k in K_VALUES},
        }
    return {"query": query, "relevant_doc_ids": relevant_doc_ids, "modes": per_mode}


def average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate_metrics(
    results: Sequence[Dict[str, Any]], modes: Sequence[str]
) -> Dict[str, Dict[str, float]]:
    aggregates: Dict[str, Dict[str, Any]] = {}
    for mode in modes:
        recalls = {k: [] for k in K_VALUES}
        precisions = {k: [] for k in K_VALUES}
        mrrs: List[float] = []
        ndcgs = {k: [] for k in K_VALUES}

        for r in results:
            mode_result = r["modes"][mode]
            for k in K_VALUES:
                recalls[k].append(mode_result["recall@k"][k])
                precisions[k].append(mode_result["precision@k"][k])
                ndcgs[k].append(mode_result["ndcg@k"][k])
            mrrs.append(mode_result["mrr"])

        aggregates[mode] = {
            f"recall@{k}": average(recalls[k]) for k in K_VALUES
        }
        aggregates[mode].update({f"precision@{k}": average(precisions[k]) for k in K_VALUES})
        aggregates[mode].update({f"ndcg@{k}": average(ndcgs[k]) for k in K_VALUES})
        aggregates[mode]["mrr"] = average(mrrs)

    return aggregates


def print_results(results: Sequence[Dict[str, Any]], aggregates: Dict[str, Dict[str, float]], modes: Sequence[str]) -> None:
    print("\n" + "=" * 80)
    print("PER-QUERY RESULTS")
    print("=" * 80)
    for r in results:
        print(f"\nQuery: {r['query']}")
        print(f"Relevant doc_ids: {sorted(r['relevant_doc_ids'])}")
        for mode in modes:
            mode_result = r["modes"][mode]
            print(f"  [{mode:8}] total={mode_result['total']}")
            print(f"    recall@k    : " + ", ".join(f"@{k}={mode_result['recall@k'][k]:.2f}" for k in K_VALUES))
            print(f"    precision@k : " + ", ".join(f"@{k}={mode_result['precision@k'][k]:.2f}" for k in K_VALUES))
            print(f"    ndcg@k      : " + ", ".join(f"@{k}={mode_result['ndcg@k'][k]:.2f}" for k in K_VALUES))
            print(f"    mrr         : {mode_result['mrr']:.2f}")

    print("\n" + "=" * 80)
    print("AGGREGATE METRICS")
    print("=" * 80)
    for mode in modes:
        print(f"\nMode: {mode}")
        for metric in ["mrr"] + [f"recall@{k}" for k in K_VALUES] + [f"precision@{k}" for k in K_VALUES] + [f"ndcg@{k}" for k in K_VALUES]:
            print(f"  {metric:12}: {aggregates[mode].get(metric, 0.0):.3f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument(
        "--reuse-kb",
        action="store_true",
        help="Reuse the existing evaluation KB instead of creating a new one",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip upload and assume the evaluation KB already contains indexed docs",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Per-channel recall count passed to the search API",
    )
    parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=10,
        help="Number of results returned after reranking",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=180,
        help="Maximum seconds to wait for document indexing",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    modes = ("hybrid", "semantic", "keyword")

    print("=" * 80)
    print("Retrieval Quality Evaluation")
    print(f"API: {BASE_URL}")
    print(f"KB : {EVAL_KB_NAME}")
    print("=" * 80)

    # Validate sample files exist.
    missing = [f for f in SAMPLE_FILES if not (SAMPLES_DIR / f).exists()]
    if missing:
        print(f"[ERROR] Missing sample files: {missing}")
        return 1

    token = login(ADMIN_USER, ADMIN_PASS)

    if args.skip_upload:
        # Find the eval KB by name.
        resp = requests.get(
            f"{BASE_URL}/api/v1/knowledge-bases",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        kb_id = None
        for kb in resp.json():
            if kb.get("name") == EVAL_KB_NAME:
                kb_id = kb["id"]
                break
        if not kb_id:
            print(f"[ERROR] Reuse requested but KB '{EVAL_KB_NAME}' not found")
            return 1
        print(f"[OK] Reusing KB {kb_id}")
    else:
        kb_id = ensure_eval_kb(token)

        # Upload sample files. Track filename -> doc_id as we go.
        print("\n[INFO] Uploading sample documents...")
        filename_to_doc_id: Dict[str, str] = {}
        for filename in SAMPLE_FILES:
            file_path = SAMPLES_DIR / filename
            try:
                doc = upload_file(token, kb_id, file_path)
                filename_to_doc_id[filename] = doc["id"]
                print(f"[OK] Uploaded {filename} -> {doc['id']}")
            except requests.HTTPError as exc:
                print(f"[ERROR] Failed to upload {filename}: {exc.response.text}")
                return 1

        # Wait for ingestion/indexing.
        if not wait_for_indexing(token, kb_id, timeout=args.wait_timeout):
            print("[ERROR] Documents did not finish indexing in time")
            return 1

    # Rebuild filename -> doc_id mapping from the backend state.
    docs = list_docs(token, kb_id)
    filename_to_doc_id = build_filename_to_doc_id(docs)
    indexed_count = sum(1 for d in docs if d.get("status") == "indexed")
    print(f"\n[INFO] KB {kb_id} has {indexed_count}/{len(docs)} indexed documents")
    if indexed_count < len(SAMPLE_FILES):
        print("[ERROR] Not all sample documents are indexed; aborting evaluation")
        return 1

    # Translate filename annotations to doc_id annotations.
    annotated_queries: List[Tuple[str, Set[str]]] = []
    for qa in QUERY_ANNOTATIONS:
        relevant_doc_ids: Set[str] = set()
        for filename in qa["expected_files"]:
            doc_id = filename_to_doc_id.get(filename)
            if not doc_id:
                print(f"[WARN] Could not map expected file '{filename}' to a doc_id")
                continue
            relevant_doc_ids.add(doc_id)
        if relevant_doc_ids:
            annotated_queries.append((qa["query"], relevant_doc_ids))

    # Run evaluation.
    print("\n[INFO] Running evaluation queries...")
    results: List[Dict[str, Any]] = []
    for query, relevant_doc_ids in annotated_queries:
        result = evaluate_query(
            token=token,
            kb_id=kb_id,
            query=query,
            relevant_doc_ids=relevant_doc_ids,
            modes=modes,
            top_k=args.top_k,
            rerank_top_k=args.rerank_top_k,
        )
        results.append(result)

    aggregates = aggregate_metrics(results, modes)
    print_results(results, aggregates, modes)

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)
    print(
        "\nNOTES ON THE BASELINE:\n"
        "  - The embedding service is a mock returning zero vectors, so semantic search\n"
        "    cannot produce meaningful rankings and hybrid search falls back to BM25.\n"
        "  - Keyword search uses PostgreSQL full-text search with the 'simple' ts_config,\n"
        "    which tokenises English/Latin terms well but does NOT segment Chinese\n"
        "    phrases. Chinese-only queries are expected to score poorly in keyword mode.\n"
        "  - This baseline is intentionally captured as-is so future improvements\n"
        "    (real embedding model, Chinese ts_config, reranker, hybrid tuning) can be\n"
        "    measured against it.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
