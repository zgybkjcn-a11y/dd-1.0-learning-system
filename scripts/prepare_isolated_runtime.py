#!/usr/bin/env python3
"""Prepare/start a mock-only disposable P0 runtime without reading root secrets.

Private runtime configuration and database inspection copies stay under /tmp.
No model requests, production changes, destructive cleanup, or old-volume writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
from pathlib import Path

from check_isolated_compose import compose_config, validate_compose_config

ROOT = Path(__file__).resolve().parents[1]
OLD_API = "dd-learning-isolated-api-20261103d"
OLD_WEBUI = "dd-openwebui-isolated-20261103d"
ENV = {"PATH": os.environ.get("PATH", "")}


def call(args: list[str], *, timeout: int = 60, stdin: str | None = None, optional: bool = False) -> str:
    result = subprocess.run(args, input=stdin, capture_output=True, text=True, env=ENV, timeout=timeout)
    if result.returncode:
        if optional and "Could not find the file" in result.stderr:
            return ""
        # Never echo Compose, environment, tokens, raw DB values or raw logs.
        reason = "docker socket permission denied" if "permission denied" in result.stderr.lower() else "command failed"
        raise RuntimeError(f"{args[0]} {args[1] if len(args) > 1 else ''}: {reason} (exit {result.returncode})")
    return (result.stdout + result.stderr).strip() if len(args) > 1 and args[1] == "logs" else result.stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict, *, private: bool = False) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600 if private else 0o644)


def emit(phase: str, **data) -> None:
    print(json.dumps({"phase": phase, **data}, ensure_ascii=False), flush=True)


def old_metadata(name: str) -> dict:
    state = json.loads(call(["docker", "inspect", "--format", "{{json .State}}", name]))
    if state["Running"]:
        raise RuntimeError("old isolated instance must remain stopped for an inspection copy")
    logs = call(["docker", "logs", "--timestamps", "--tail", "300", name])
    patterns = {
        "traceback": "Traceback (most recent call last)",
        "application_shutdown": "Application shutdown complete",
        "uvicorn_started": "Uvicorn running on",
        "sigterm": "SIGTERM",
        "sqlite_operational_error": "sqlite3.OperationalError",
    }
    return {
        "container": name,
        "state": {key: state[key] for key in ("Status", "Running", "ExitCode", "OOMKilled", "FinishedAt")},
        "image_id": call(["docker", "inspect", "--format", "{{.Image}}", name]),
        "log_pattern_counts": {key: logs.count(pattern) for key, pattern in patterns.items()},
        "stop_cause": "unknown; exit code and bounded log patterns are insufficient",
    }


def inspection_copy(name: str, source: str, destination: Path) -> dict:
    destination.mkdir(mode=0o700)
    for suffix in ("", "-wal", "-shm"):
        target = destination / (Path(source).name + suffix)
        call(["docker", "cp", f"{name}:{source}{suffix}", str(target)], optional=bool(suffix))
        if target.exists():
            target.chmod(0o600)
    return {path.name: digest(path) for path in destination.iterdir() if path.is_file()}


def prepare(run_dir: Path, project: str) -> None:
    # Existing preflight reads only the explicit learning Compose; never .env.
    config = compose_config()
    errors = validate_compose_config(config)
    if errors:
        raise RuntimeError("tracked Compose isolation preflight failed: " + "; ".join(errors))
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError("runtime directory is not empty; existing files are preserved")
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_dir.chmod(0o700)
    old = {"api": old_metadata(OLD_API), "webui": old_metadata(OLD_WEBUI)}
    backups = run_dir / "inspection-copies"
    backups.mkdir(mode=0o700)
    old["api"]["inspection_files"] = inspection_copy(OLD_API, "/var/lib/dd-learning/learning.db", backups / "api")
    old["webui"]["inspection_files"] = inspection_copy(OLD_WEBUI, "/app/backend/data/webui.db", backups / "webui")
    with sqlite3.connect(f"file:{backups / 'api/learning.db'}?mode=ro", uri=True) as db:
        old["api"]["schema_revision"] = db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    with sqlite3.connect(f"file:{backups / 'webui/webui.db'}?mode=ro", uri=True) as db:
        row = db.execute("SELECT content FROM tool WHERE id=?", ("dd_learning_v1",)).fetchone()
        old["webui"]["tool_sha256"] = hashlib.sha256(row[0].encode()).hexdigest() if row else None
    # These are SQLite inspection copies, not a complete DB/attachment backup.
    context = run_dir / "build-context"
    context.mkdir()
    sources = [ROOT / "Dockerfile.learning", ROOT / "requirements-learning.txt"]
    sources += sorted(path for path in (ROOT / "learning_service").rglob("*") if path.suffix in {".py", ".sql"})
    fingerprints = {}
    for source in sources:
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise RuntimeError("build source must be a regular repository file")
        relative = source.relative_to(ROOT)
        target = context / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        fingerprints[str(relative)] = digest(target)
    image = f"dd-learning:{project}"
    for service in config["services"].values():
        service["image"] = image
        service.pop("build", None)
        service["restart"] = "no"
        service["pull_policy"] = "never"
        service["environment"]["TENCENT_OCR_EXTERNAL_CALLS_ENABLED"] = "0"
        service["environment"]["TENCENT_OCR_SECRET_ID"] = ""
        service["environment"]["TENCENT_OCR_SECRET_KEY"] = ""
    api_env = config["services"]["learning-api"]["environment"]
    for name, definition in config["networks"].items():
        definition["name"] = f"{project}_{name}"
    config["volumes"]["dd_learning_data"]["name"] = f"{project}_dd_learning_data"
    config["volumes"]["dd_openwebui_data"] = {"name": f"{project}_dd_openwebui_data"}
    config["name"] = project
    config["services"]["open-webui"] = {
        "image": old["webui"]["image_id"], "pull_policy": "never", "restart": "no",
        "networks": {"learning-internal": None},
        "volumes": [{"type": "volume", "source": "dd_openwebui_data", "target": "/app/backend/data"}],
        "environment": {
            "OFFLINE_MODE": "true", "HF_HUB_OFFLINE": "1", "DO_NOT_TRACK": "true",
            "ENABLE_OPENAI_API": "false", "ENABLE_OLLAMA_API": "false",
            "ENABLE_PERSISTENT_CONFIG": "false", "ENABLE_VERSION_UPDATE_CHECK": "false",
            "ENABLE_COMMUNITY_SHARING": "false", "ENABLE_EVALUATION_ARENA_MODELS": "false",
            "RAG_EMBEDDING_MODEL_AUTO_UPDATE": "false", "RAG_RERANKING_MODEL_AUTO_UPDATE": "false",
            "WHISPER_MODEL_AUTO_UPDATE": "false", "ANONYMIZED_TELEMETRY": "false",
            "SCARF_NO_ANALYTICS": "true", "ENABLE_SIGNUP": "false", "WEBUI_AUTH": "true",
            "WEBUI_SECRET_KEY": secrets.token_urlsafe(32),
            "WEBUI_ADMIN_EMAIL": "dd-p0-admin@example.invalid", "WEBUI_ADMIN_NAME": "DD P0 Synthetic Admin",
            "WEBUI_ADMIN_PASSWORD": secrets.token_urlsafe(32),
            "DD_LEARNING_ADAPTER_SECRET": api_env["LEARNING_ADAPTER_SECRET"],
        },
    }
    save(run_dir / "compose.private.json", config, private=True)
    save(run_dir / "manifest.json", {
        "project": project, "learning_image": image, "open_webui_image": old["webui"]["image_id"],
        "source_sha256": fingerprints, "old_instances": old,
        "tool_matches_old_registration": old["webui"]["tool_sha256"] == fingerprints["learning_service/tools.py"],
        "external_calls": False, "host_ports": False, "inspection_copy_is_full_backup": False,
        "compose_sha256": digest(run_dir / "compose.private.json"),
    })
    emit("prepared", run_dir=str(run_dir), project=project, source_files=len(fingerprints),
         old_schema=old["api"]["schema_revision"], tool_matches_old=old["webui"]["tool_sha256"] == fingerprints["learning_service/tools.py"])


def compose(run_dir: Path, *arguments: str, timeout: int = 120) -> str:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    if digest(run_dir / "compose.private.json") != manifest["compose_sha256"]:
        raise RuntimeError("private Compose changed; prepare a separately reviewed runtime")
    if not re.fullmatch(r"dd-learning-p0-[a-z0-9-]+", manifest["project"]):
        raise RuntimeError("invalid disposable project in manifest")
    return call(["docker", "compose", "--env-file", "/dev/null", "-p", manifest["project"],
                 "-f", str(run_dir / "compose.private.json"), *arguments], timeout=timeout)


def container(run_dir: Path, service: str) -> str:
    value = compose(run_dir, "ps", "-q", service)
    if not value or "\n" in value:
        raise RuntimeError(f"expected exactly one running {service}")
    return value


def start(run_dir: Path) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    existing = call(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={manifest['project']}"])
    volumes = call(["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={manifest['project']}"])
    networks = call(["docker", "network", "ls", "-q", "--filter", f"label=com.docker.compose.project={manifest['project']}"])
    if existing or volumes or networks:
        raise RuntimeError("project already has resources; existing runtime is preserved (use resume)")
    base_id = call(["docker", "image", "inspect", "--format", "{{.Id}}", "dd-learning:local"])
    expected = {}
    for line in (run_dir / "build-context/requirements-learning.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==", 1)
            expected[name] = version
    dependency_probe = "import importlib.metadata,json; print(json.dumps({n:importlib.metadata.version(n) for n in " + repr(list(expected)) + "}))"
    actual = json.loads(call(["docker", "run", "--rm", "--network", "none", "--pull=never",
                              "--entrypoint", "python", base_id, "-c", dependency_probe]))
    if actual != expected:
        raise RuntimeError("cached base dependencies do not match pinned requirements; no downloads permitted")
    base_tag = f"dd-learning:{manifest['project']}-base"
    call(["docker", "tag", base_id, base_tag])
    offline_dockerfile = run_dir / "build-context/Dockerfile.p0"
    offline_dockerfile.write_text(f"FROM {base_tag}\nWORKDIR /app\nCOPY learning_service /app/learning_service\n")
    manifest["cached_base_image_id"] = base_id
    manifest["cached_base_dependencies"] = actual
    manifest["offline_dockerfile_sha256"] = digest(offline_dockerfile)
    save(run_dir / "manifest.json", manifest)
    emit("building", network="none", source="minimal copied context", cached_base=base_id)
    call(["docker", "build", "--network", "none", "--pull=false", "-f",
          str(offline_dockerfile), "-t", manifest["learning_image"],
          str(run_dir / "build-context")], timeout=300)
    emit("starting", project=manifest["project"])
    compose(run_dir, "up", "-d", "--no-build", "--pull", "never", timeout=180)
    emit("started", project=manifest["project"])


def verify(run_dir: Path) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    config = json.loads((run_dir / "compose.private.json").read_text())
    project = manifest["project"]
    network = json.loads(call(["docker", "network", "inspect", f"{project}_learning-internal"]))[0]
    assert network["Internal"] is True
    summaries = {}
    for name in config["services"]:
        cid = container(run_dir, name)
        mounts = json.loads(call(["docker", "inspect", "--format", "{{json .Mounts}}", cid]))
        networks = json.loads(call(["docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", cid]))
        ports = json.loads(call(["docker", "inspect", "--format", "{{json .HostConfig.PortBindings}}", cid]))
        assert set(networks) == {f"{project}_learning-internal"} and not ports
        assert len(mounts) == 1 and mounts[0]["Type"] == "volume" and mounts[0]["Name"].startswith(project + "_")
        summaries[name] = {"container_id": cid, "image_id": call(["docker", "inspect", "--format", "{{.Image}}", cid]),
                           "volume": mounts[0]["Name"], "published_ports": False}
    api_container = container(run_dir, "learning-api")
    source_probe = ("import hashlib,json\nfrom pathlib import Path\n"
                    "root=Path('/app')\n"
                    "print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() "
                    "for p in (root/'learning_service').rglob('*') if p.suffix in {'.py','.sql'}}))\n")
    actual_sources = json.loads(call(["docker", "exec", "-i", api_container, "python", "-"], stdin=source_probe))
    assert actual_sources == {p: h for p, h in manifest["source_sha256"].items() if p.startswith("learning_service/")}
    call(["docker", "cp", str(ROOT / "docs/contracts/openapi-v1.json"), f"{api_container}:/tmp/dd-p0-openapi.json"])
    probe = call(["docker", "exec", "-i", container(run_dir, "learning-api"), "python", "-"], timeout=180,
                 stdin=(ROOT / "scripts/isolated_runtime_probe.py").read_text())
    result = json.loads(probe.splitlines()[-1])
    result["runtime_source_matches_snapshot"] = True
    save(run_dir / "verification.json", {"project": project, "network_internal": True, "services": summaries, **result})
    emit("verified", **result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "start", "resume", "verify", "tools", "check-tools", "stop"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--project", default="dd-learning-p0-20261104")
    args = parser.parse_args()
    if not re.fullmatch(r"dd-learning-p0-[a-z0-9-]+", args.project):
        raise SystemExit("project must use the dd-learning-p0- prefix")
    run_dir = args.run_dir.resolve()
    if not run_dir.is_relative_to(Path("/tmp")) or run_dir == Path("/tmp"):
        raise SystemExit("runtime files must stay in a dedicated /tmp directory")
    if args.action == "prepare":
        prepare(run_dir, args.project)
    else:
        if args.action == "start":
            start(run_dir)
        elif args.action == "resume":
            compose(run_dir, "up", "-d", "--no-build", "--pull", "never", timeout=180)
            emit("resumed", old_instances_unchanged=True)
        elif args.action == "verify":
            verify(run_dir)
        elif args.action == "tools":
            if not (run_dir / "verification.json").is_file():
                raise RuntimeError("verify runtime boundaries before preparing Tool identity")
            ow = container(run_dir, "open-webui")
            manifest = json.loads((run_dir / "manifest.json").read_text())
            source = run_dir / "build-context/learning_service/tools.py"
            assert digest(source) == manifest["source_sha256"]["learning_service/tools.py"]
            call(["docker", "cp", str(source), f"{ow}:/tmp/dd-p0-tools.py"])
            call(["docker", "cp", str(ROOT / "scripts/isolated_tool_probe.py"), f"{ow}:/tmp/dd-p0-tool-probe.py"])
            registration = json.loads(call(["docker", "exec", ow, "python", "/tmp/dd-p0-tool-probe.py", "register"]).splitlines()[-1])
            seed = ("from learning_service.config import Settings\nfrom learning_service.db import Database,utc_now\n"
                    "with Database(Settings.from_env().db_path).session(write=True) as db:\n"
                    " db.execute('INSERT OR IGNORE INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES (?,?,?,?,?,?)', "
                    + repr(("p0-webui-admin", "p0-account-a", "open-webui", "dd-p0", registration["user_id"]))
                    + "+(utc_now(),))\n")
            call(["docker", "exec", "-i", container(run_dir, "learning-api"), "python", "-"], stdin=seed)
            result = json.loads(call(["docker", "exec", ow, "python", "/tmp/dd-p0-tool-probe.py", "load"], timeout=90).splitlines()[-1])
            save(run_dir / "tools-verification.json", {**result, "model_count": registration["model_count"]})
            emit("tools_verified", **result, model_count=registration["model_count"])
        elif args.action == "check-tools":
            result = json.loads(call(["docker", "exec", container(run_dir, "open-webui"), "python",
                                      "/tmp/dd-p0-tool-probe.py", "load"], timeout=90).splitlines()[-1])
            previous = json.loads((run_dir / "tools-verification.json").read_text())
            assert result["tool_sha256"] == previous["tool_sha256"]
            emit("persisted_tools_verified", **result)
        else:
            compose(run_dir, "stop")
            emit("stopped", volumes_preserved=True)


if __name__ == "__main__":
    main()
