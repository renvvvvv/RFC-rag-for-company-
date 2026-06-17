# Backend Performance / Load Tests

This directory contains a Locust-based load test suite for the Enterprise Private RAG backend FastAPI API.

## What is covered

| User class            | Weight | Endpoints exercised                          |
|-----------------------|--------|---------------------------------------------|
| `HealthCheckUser`     | 5      | `GET /api/v1/health`                        |
| `AuthUser`            | 3      | `POST /api/v1/auth/login`, `GET /api/v1/auth/me` |
| `KnowledgeBaseUser`   | 5      | `GET /api/v1/knowledge-bases`, `GET /api/v1/knowledge-bases/{id}/stats` |
| `SearchUser`          | 10     | `POST /api/v1/search`, `/search/semantic`, `/search/keyword`, `GET /api/v1/search/history` |
| `ChatUser`            | 5      | `POST /api/v1/chat` (non-streaming)         |
| `DocumentUploadUser`  | 1      | `POST /api/v1/documents`                    |

The suite is self-contained: on start it logs in as `admin`, picks an existing knowledge base with indexed documents (or creates one and waits for indexing), ensures a low-security test user exists, and points the runtime LLM config at the mock LLM service.

## Setup

The dedicated virtual environment is already created under `scripts/perf/.venv`. If you need to recreate it:

```bash
python -m venv scripts/perf/.venv
scripts/perf/.venv/Scripts/python -m pip install -r scripts/perf/requirements.txt
```

## Run

Default headless run (50 users, ramp 5/s, 60 s):

```bash
bash scripts/perf/run.sh
```

Override defaults via environment variables:

```bash
RAG_USERS=100 RAG_DURATION=120s RAG_HOST=http://localhost:8080 bash scripts/perf/run.sh
```

Or run the Python entrypoint directly:

```bash
scripts/perf/.venv/Scripts/python scripts/perf/run_load_test.py -u 50 -r 5 -t 60s
```

## Outputs

After a run, results are written to `scripts/perf/results/`:

- `locust_stats.csv` – aggregate request stats
- `locust_failures.csv` – failure details
- `locust_stats_history.csv` – per-interval RPS/latency history
- `report.html` – Locust HTML report

Use these CSVs to compute aggregate RPS, p50/p95/p99 latency, and failure rate.

## Configuration

| Environment variable | Default              | Description                  |
|----------------------|----------------------|------------------------------|
| `RAG_HOST`           | `http://localhost:8080` | Target API host             |
| `RAG_USERS`          | `50`                 | Simulated users              |
| `RAG_SPAWN_RATE`     | `5`                  | Users spawned per second     |
| `RAG_DURATION`       | `60`                 | Test duration                |
| `RAG_ADMIN_USER`     | `admin`              | Admin username               |
| `RAG_ADMIN_PASS`     | `admin123`           | Admin password               |
| `RAG_TEST_USER`      | `loadtest_user`      | Low-security chat test user  |
| `RAG_TEST_PASS`      | `Test1234!`          | Chat test user password      |
