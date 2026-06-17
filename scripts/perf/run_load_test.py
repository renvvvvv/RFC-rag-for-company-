"""Headless Locust runner that captures aggregate stats and exits.

Usage:
    scripts/perf/.venv/Scripts/python scripts/perf/run_load_test.py [options]

Environment variables:
    RAG_HOST            Target host (default: http://localhost:8080)
    RAG_USERS           Number of simulated users (default: 50)
    RAG_SPAWN_RATE      Users spawned per second (default: 5)
    RAG_DURATION        Test duration in seconds (default: 60)
    RAG_ADMIN_USER      Admin username (default: admin)
    RAG_ADMIN_PASS      Admin password (default: admin123)
    RAG_CSV_PREFIX      CSV stats prefix (default: scripts/perf/results/locust)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


DEFAULTS = {
    "host": os.environ.get("RAG_HOST", "http://localhost:8080"),
    "users": os.environ.get("RAG_USERS", "50"),
    "spawn_rate": os.environ.get("RAG_SPAWN_RATE", "5"),
    "duration": os.environ.get("RAG_DURATION", "60"),
    "csv_prefix": os.environ.get("RAG_CSV_PREFIX", str(Path(__file__).parent / "results" / "locust")),
}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the RAG backend load test")
    parser.add_argument("--host", default=DEFAULTS["host"], help="Target API host")
    parser.add_argument("-u", "--users", default=DEFAULTS["users"], help="Number of users")
    parser.add_argument("-r", "--spawn-rate", default=DEFAULTS["spawn_rate"], help="Spawn rate")
    parser.add_argument("-t", "--duration", default=DEFAULTS["duration"], help="Duration, e.g. 60s")
    parser.add_argument("--csv-prefix", default=DEFAULTS["csv_prefix"], help="CSV output prefix")
    parser.add_argument("--locustfile", default=str(Path(__file__).parent / "locustfile.py"))
    args = parser.parse_args()

    results_dir = Path(args.csv_prefix).parent
    results_dir.mkdir(parents=True, exist_ok=True)

    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = Path(__file__).parent / ".venv" / "bin" / "python"

    cmd = [
        str(venv_python),
        "-m",
        "locust",
        "-f",
        args.locustfile,
        "--host",
        args.host,
        "--headless",
        "-u",
        args.users,
        "-r",
        args.spawn_rate,
        "-t",
        args.duration,
        "--csv",
        args.csv_prefix,
        "--csv-full-history",
        "--html",
        str(results_dir / "report.html"),
        "--exit-code-on-error",
        "0",
    ]

    print("Running load test...")
    print(" ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
