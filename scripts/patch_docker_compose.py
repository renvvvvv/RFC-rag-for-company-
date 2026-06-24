"""Patch docker-compose*.yml files with resource limits and monitoring profiles."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

RESOURCE_LIMITS = {
    # Application layer
    "kong": {"cpus": "1.0", "memory": "1.5g"},
    "migrate": {"cpus": "0.5", "memory": "512m"},
    "app-backend": {"cpus": "1.0", "memory": "1g"},
    "ingest-worker": {"cpus": "1.0", "memory": "1.5g"},
    "embed-worker": {"cpus": "1.0", "memory": "1.5g"},
    "permission-sync-worker": {"cpus": "0.5", "memory": "1.5g"},
    "embedding-service": {"cpus": "0.5", "memory": "256m"},
    "llm-service": {"cpus": "0.5", "memory": "256m"},
    "frontend": {"cpus": "0.25", "memory": "128m"},
    # Infrastructure layer
    "postgres": {"cpus": "0.5", "memory": "1g"},
    "redis": {"cpus": "0.25", "memory": "256m"},
    "rabbitmq": {"cpus": "0.5", "memory": "512m"},
    "milvus-standalone": {"cpus": "2.0", "memory": "2g"},
    "etcd": {"cpus": "0.5", "memory": "512m"},
    "minio": {"cpus": "0.5", "memory": "512m"},
    "minio-init": {"cpus": "0.25", "memory": "256m"},
    # Monitoring
    "prometheus": {"cpus": "0.5", "memory": "512m"},
    "alertmanager": {"cpus": "0.25", "memory": "256m"},
    "grafana": {"cpus": "0.5", "memory": "512m"},
    "postgres-exporter": {"cpus": "0.25", "memory": "128m"},
    "redis-exporter": {"cpus": "0.25", "memory": "128m"},
    "rabbitmq-exporter": {"cpus": "0.25", "memory": "128m"},
    "node-exporter": {"cpus": "0.25", "memory": "128m"},
}

MONITORING_PROFILES = {"prometheus", "alertmanager", "grafana"}


def indent(level: int) -> str:
    return "  " * level


def deploy_block(service: str, service_indent: int) -> list[str]:
    """Return a deploy block at the same indentation as other service properties."""
    limits = RESOURCE_LIMITS.get(service, {"cpus": "0.5", "memory": "512m"})
    # Service name is at `service_indent` spaces; properties are service_indent + 2 spaces.
    # indent(level) returns 2*level spaces.
    base_level = (service_indent + 2) // 2
    return [
        f"{indent(base_level)}deploy:",
        f"{indent(base_level + 1)}resources:",
        f"{indent(base_level + 2)}limits:",
        f"{indent(base_level + 3)}cpus: '{limits['cpus']}'",
        f"{indent(base_level + 3)}memory: {limits['memory']}",
        f"{indent(base_level + 2)}reservations:",
        f"{indent(base_level + 3)}memory: 64m",
    ]


def patch_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out_lines: list[str] = []

    current_service: str | None = None
    service_level: int | None = None
    in_services_section = False
    inserted_deploy_for_current = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        level = len(line) - len(stripped)

        # Track whether we are inside the top-level `services:` mapping
        if level == 0 and re.match(r"^services:\s*$", stripped):
            in_services_section = True
        elif level == 0 and stripped and not stripped.startswith("#") and ":" in stripped:
            in_services_section = False

        # Detect a service key inside `services:` (level 2, simple key)
        is_service_key = (
            in_services_section
            and level == 2
            and stripped
            and not stripped.startswith("#")
            and re.match(r"^[a-z0-9_-]+:\s*$", stripped)
        )

        # If we are about to start a new service (or leave services section),
        # close the previous service with a deploy block.
        if (
            current_service is not None
            and not inserted_deploy_for_current
            and (is_service_key or not in_services_section)
        ):
            out_lines.extend(deploy_block(current_service, service_level))
            inserted_deploy_for_current = True
            current_service = None

        if is_service_key:
            current_service = stripped.rstrip(":").strip()
            service_level = level
            inserted_deploy_for_current = False

        # Add monitoring profile immediately under the service name line
        if (
            current_service in MONITORING_PROFILES
            and is_service_key
        ):
            out_lines.append(line)
            # profiles is a service-level property, same indent as build/networks/etc.
            profile_level = (service_level + 2) // 2
            out_lines.append(f"{indent(profile_level)}profiles:")
            out_lines.append(f"{indent(profile_level + 1)}- monitoring")
            i += 1
            continue

        out_lines.append(line)
        i += 1

    # Close the final service if needed
    if current_service is not None and not inserted_deploy_for_current:
        out_lines.extend(deploy_block(current_service, service_level))

    out_text = "\n".join(out_lines)

    # Ensure ingest-worker uses the dedicated ingest Dockerfile
    out_text = re.sub(
        r"(ingest-worker:[\s\S]*?dockerfile:\s*)Dockerfile\.worker",
        r"\1Dockerfile.ingest",
        out_text,
    )

    path.write_text(out_text + "\n", encoding="utf-8")
    print(f"Patched {path}")


def main():
    for name in ["docker-compose.yml", "docker-compose.app.yml", "docker-compose.infra.yml"]:
        path = ROOT / name
        if path.exists():
            patch_file(path)
        else:
            print(f"Skip missing {path}")


if __name__ == "__main__":
    main()
