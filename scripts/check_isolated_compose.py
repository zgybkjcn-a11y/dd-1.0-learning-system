#!/usr/bin/env python3
"""Validate the tracked Learning Service Compose file without starting it."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.learning.yml"
EXPECTED_SERVICES = {"learning-api", "learning-worker"}
EXPECTED_PROVIDER_IDS = {
    "LEARNING_DOCUMENT_PROVIDER": "mock-document-v1",
    "LEARNING_DIAGNOSIS_PROVIDER": "mock-diagnosis-v1",
    "LEARNING_VARIANT_PROVIDER": "mock-variant-v1",
}


def validate_compose_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    services = config.get("services")
    if not isinstance(services, dict) or set(services) != EXPECTED_SERVICES:
        return ["service set must contain only learning-api and learning-worker"]

    networks = config.get("networks")
    if not isinstance(networks, dict) or set(networks) != {"learning-internal"}:
        errors.append("only the learning-internal network is allowed")
    elif networks["learning-internal"].get("internal") is not True or networks["learning-internal"].get("external") is True:
        errors.append("learning-internal must be an isolated, non-external network")

    volumes = config.get("volumes")
    if not isinstance(volumes, dict) or set(volumes) != {"dd_learning_data"}:
        errors.append("only the named dd_learning_data volume is allowed")
    elif volumes["dd_learning_data"].get("external") is True or volumes["dd_learning_data"].get("driver_opts"):
        errors.append("dd_learning_data must be a Compose-managed volume without host driver options")

    for service_name, service in services.items():
        if not isinstance(service, dict):
            errors.append(f"{service_name} configuration must be an object")
            continue
        if service.get("ports"):
            errors.append(f"{service_name} must not publish host ports")
        if service.get("privileged") is True:
            errors.append(f"{service_name} must not run privileged")
        if service.get("network_mode") in {"host", "service:learning-api", "service:learning-worker"}:
            errors.append(f"{service_name} must not bypass the isolated network")
        if service.get("pid") == "host" or service.get("ipc") == "host" or service.get("userns_mode") == "host":
            errors.append(f"{service_name} must not share host namespaces")
        for field in ("devices", "cap_add", "volumes_from"):
            if service.get(field):
                errors.append(f"{service_name} must not configure {field}")

        service_networks = service.get("networks")
        if not isinstance(service_networks, dict) or set(service_networks) != {"learning-internal"}:
            errors.append(f"{service_name} must attach only to learning-internal")

        mounts = service.get("volumes") or []
        if len(mounts) != 1 or not isinstance(mounts[0], dict) or mounts[0].get("type") != "volume" or mounts[0].get("source") != "dd_learning_data" or mounts[0].get("target") != "/var/lib/dd-learning":
            errors.append(f"{service_name} must use only the managed dd_learning_data volume")

        environment = service.get("environment")
        if not isinstance(environment, dict):
            errors.append(f"{service_name} must declare an environment map")
            continue
        if str(environment.get("LEARNING_DEV_MODE", "")).lower() not in {"0", "false"}:
            errors.append(f"{service_name} must run with development mode disabled")
        for variable, expected in EXPECTED_PROVIDER_IDS.items():
            if environment.get(variable) != expected:
                errors.append(f"{service_name} must use the deterministic {variable} provider")

    api = services.get("learning-api", {})
    if api.get("image") != "dd-learning:local":
        errors.append("learning-api must use the local Learning Service image")
    build = api.get("build")
    if not isinstance(build, dict) or Path(str(build.get("context", ""))).resolve() != ROOT or build.get("dockerfile") != "Dockerfile.learning":
        errors.append("learning-api must build only from this repository's Dockerfile.learning")
    worker = services.get("learning-worker", {})
    if worker.get("image") != api.get("image"):
        errors.append("learning-worker must use the same local image as learning-api")
    return errors


def compose_config() -> dict[str, Any]:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "LEARNING_ADMIN_SECRET": secrets.token_urlsafe(32),
        "LEARNING_ADAPTER_SECRET": secrets.token_urlsafe(32),
    }
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "-f",
            str(COMPOSE_FILE),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose config failed with exit code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("docker compose config returned invalid JSON") from exc


def main() -> int:
    try:
        config = compose_config()
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"Isolation preflight could not inspect Compose: {exc}", file=sys.stderr)
        return 2

    errors = validate_compose_config(config)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("Isolation preflight passed: 2 services, internal network, managed volume, mock providers, no published ports.")
    print("No containers were started; external provider and service fault drills remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
