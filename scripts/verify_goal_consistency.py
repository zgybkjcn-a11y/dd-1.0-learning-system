#!/usr/bin/env python3
"""Check DD-1.0 task, QA, and release-manifest references using stdlib only."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TASKS = {f"T{i:02d}" for i in range(1, 27)}
EXPECTED_QA = {f"QA{i:02d}" for i in range(1, 18)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def require_repo_path(value: str, label: str) -> None:
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts, f"{label}: unsafe repo path {value!r}")
    resolved = (ROOT / path).resolve()
    require(resolved.is_relative_to(ROOT), f"{label}: path escapes project root: {value!r}")
    require(resolved.exists(), f"{label}: missing path {value!r}")


def main() -> None:
    task_doc = json.loads((ROOT / "docs/goal/TASKS.json").read_text(encoding="utf-8"))
    tasks = task_doc["tasks"]
    require(set(tasks) == EXPECTED_TASKS, "TASKS.json must contain exactly T01-T26")
    status_text = (ROOT / "docs/goal/STATUS.md").read_text(encoding="utf-8")
    status_match = re.search(r"^Goal：`([^`]+)`（(active|blocked)）$", status_text, flags=re.MULTILINE)
    require(status_match is not None, "STATUS.md must record the Goal ID and active/blocked state")
    require(status_match.group(1) == task_doc["goal_id"], "STATUS.md and task goal IDs differ")
    expected_manifest_status = {
        "active": "goal_active_not_complete",
        "blocked": "goal_blocked_not_complete",
    }[status_match.group(2)]
    evidence_count = 0
    for task_id, task in tasks.items():
        for evidence in task.get("evidence", []):
            require_repo_path(evidence, f"{task_id} evidence")
            evidence_count += 1

    backlog = (ROOT / "docs/IMPLEMENTATION_BACKLOG.md").read_text(encoding="utf-8")
    backlog_tasks = set(re.findall(r"^\| (T\d{2}) \|", backlog, flags=re.MULTILINE))
    require(backlog_tasks == EXPECTED_TASKS, "backlog must contain exactly T01-T26 rows")
    backlog_qa = {f"QA{number}" for number in re.findall(r"QA(\d{2})", backlog)}
    require(EXPECTED_QA <= backlog_qa, "backlog is missing one or more QA01-QA17 references")

    qa_matrix = (ROOT / "docs/verification/qa-matrix-2026-11-03.md").read_text(encoding="utf-8")
    matrix_qa = set(re.findall(r"^\| (QA\d{2}) ", qa_matrix, flags=re.MULTILINE))
    require(matrix_qa == EXPECTED_QA, "QA matrix must contain exactly QA01-QA17 rows")

    manifest = json.loads(
        (ROOT / "docs/verification/release-manifest-2026-11-03.json").read_text(encoding="utf-8")
    )
    require(manifest["goal_id"] == task_doc["goal_id"], "release manifest and task goal IDs differ")
    require(manifest["status"] == expected_manifest_status, "manifest must reflect the documented non-complete Goal state")
    for name in ("production_cutover", "real_student_data_export", "paid_provider_calls"):
        require(manifest["approval"][name] == "not_authorized", f"unexpected release authorization: {name}")

    path_fields = (
        ("components.open_webui_baseline.source", manifest["components"]["open_webui_baseline"]["source"]),
        ("components.learning_service.source", manifest["components"]["learning_service"]["source"]),
        ("components.runtime.image_definition", manifest["components"]["runtime"]["image_definition"]),
        ("components.runtime.compose_definition", manifest["components"]["runtime"]["compose_definition"]),
        ("components.dependencies.lock_file", manifest["components"]["dependencies"]["lock_file"]),
    )
    for label, value in path_fields:
        require_repo_path(value, f"manifest {label}")

    manifest_evidence = manifest["evidence"]
    test_summary = manifest_evidence.get("automated_tests", "")
    require(test_summary.startswith("pytest -q:"), "manifest automated_tests must remain a result description")
    manifest_evidence_paths = 0
    for name, value in manifest_evidence.items():
        if name == "automated_tests":
            continue
        require(isinstance(value, str), f"manifest evidence {name} must be a string")
        # Some values add human-readable metadata after the path in parentheses.
        path = value.split(" (", 1)[0]
        require_repo_path(path, f"manifest evidence {name}")
        manifest_evidence_paths += 1

    print(
        f"tasks={len(tasks)}, evidence paths={evidence_count}, "
        f"backlog task rows={len(backlog_tasks)}, QA matrix rows={len(matrix_qa)}, "
        f"manifest path references={len(path_fields) + manifest_evidence_paths}, "
        "release authorization boundaries intact"
    )


if __name__ == "__main__":
    main()
