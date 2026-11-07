#!/usr/bin/env python3
"""Validate a rendered sidecar without reading implicit .env or starting it."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy/open-webui-reuse/compose.learning-sidecar.yml"


def compose_config(image: str, secret_directory: Path) -> dict:
    env = {"PATH": os.environ.get("PATH", ""), "DD_LEARNING_IMAGE": image,
           "DD_SECRET_DIRECTORY": str(secret_directory)}
    p = subprocess.run(["docker", "compose", "--env-file", "/dev/null", "-f", str(COMPOSE),
                        "config", "--format", "json"], env=env, cwd=ROOT,
                       capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise ValueError("explicit sidecar rendering failed")
    return json.loads(p.stdout)


def validate(config: dict, *, isolated: bool = False) -> list[str]:
    errors = []
    services = config.get("services", {})
    expected = {"learning-api", "learning-worker", "learning-gateway", "learning-proxy"}
    if isolated:
        expected.add("open-webui")
    if set(services) != expected:
        errors.append("unexpected service set")
    for name, service in services.items():
        if service.get("build") or not re.fullmatch(r"(?:sha256:[a-f0-9]{64}|[^\s]+@sha256:[a-f0-9]{64})", service.get("image", "")):
            errors.append(name + ": image must be fixed, with no build context")
        if service.get("ports") and (isolated or name != "learning-proxy"):
            errors.append(name + ": host port publication rejected")
        if any(service.get(k) for k in ("privileged", "network_mode", "pid", "ipc", "devices", "cap_add", "volumes_from")):
            errors.append(name + ": namespace or capability bypass rejected")
        if name != "open-webui" and (service.get("read_only") is not True or service.get("cap_drop") != ["ALL"]):
            errors.append(name + ": read-only and capability restrictions required")
        for mount in service.get("volumes", []):
            if mount.get("type") != "volume" or mount.get("source") not in {"dd_learning_data", "dd_webui_data"}:
                errors.append(name + ": unexpected data mount")
        nets = set(service.get("networks", {}))
        wanted = {"learning-internal"} if name in {"learning-api", "learning-worker"} else {"learning-internal", "webui-upstream"}
        if name == "open-webui":
            wanted = {"learning-internal", "webui-upstream"}
        if nets != wanted:
            errors.append(name + ": unexpected network attachment")
    nets = config.get("networks", {})
    if set(nets) != {"learning-internal", "webui-upstream"} or nets.get("learning-internal", {}).get("internal") is not True:
        errors.append("dedicated internal learning network required")
    if isolated:
        if any(n.get("external") or n.get("internal") is not True for n in nets.values()):
            errors.append("isolated networks must be new and internal")
        if any(v.get("external") or v.get("driver_opts") for v in config.get("volumes", {}).values()):
            errors.append("isolated volumes must be Compose-managed")
    elif nets.get("webui-upstream", {}).get("name") != "open-webui_default" or not nets.get("webui-upstream", {}).get("external"):
        errors.append("existing upstream network must be an explicit external reference")
    api = services.get("learning-api", {})
    worker = services.get("learning-worker", {})
    if api.get("image") != worker.get("image") or api.get("environment") != worker.get("environment"):
        errors.append("API and worker runtime settings differ")
    env = api.get("environment", {})
    for k, v in {"LEARNING_DEV_MODE":"0", "LEARNING_DOCUMENT_PROVIDER":"mock-document-v1",
                 "LEARNING_DIAGNOSIS_PROVIDER":"mock-diagnosis-v1", "LEARNING_VARIANT_PROVIDER":"mock-variant-v1",
                 "LEARNING_MODEL_EXTERNAL_CALLS_ENABLED":"0", "TENCENT_OCR_EXTERNAL_CALLS_ENABLED":"0",
                 "LEARNING_PROVIDER_TOTAL_BUDGET_MICROS":"0", "LEARNING_PROVIDER_DAILY_BUDGET_MICROS":"0",
                 "LEARNING_PROVIDER_MAX_COST_MICROS_PER_CALL":"0", "LEARNING_PROVIDER_MAX_CALLS_PER_DAY":"0",
                 "LEARNING_PROVIDER_MAX_CALLS_PER_MINUTE":"0", "LEARNING_SHARED_LEARNER_CONTEXT_ENABLED":"1",
                 "LEARNING_PUBLIC_BASE_PATH":"/learning"}.items():
        if str(env.get(k, "")) != v:
            errors.append(k + ": restricted mock configuration required")
    for name in ("LEARNING_ADMIN_SECRET", "LEARNING_ADAPTER_SECRET", "LEARNING_BROWSER_AUTH_SECRET"):
        if env.get(name) or env.get(name + "_FILE") != "/run/secrets/" + name.lower():
            errors.append(name + ": explicit secret reference required")
    return errors


if __name__ == "__main__":
    # Rendering references does not open the referenced files.
    result = validate(compose_config("sha256:" + "0" * 64, ROOT / "learning_data/unconfigured-secrets"))
    print(json.dumps({"errors": result, "started_containers": False}))
    raise SystemExit(bool(result))
