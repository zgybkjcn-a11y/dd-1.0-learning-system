#!/usr/bin/env python3
"""Seal a whitelisted source candidate; never build, publish, or deploy it."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = ("__init__", "app", "backup", "browser_auth", "config", "db", "model_providers",
           "provider_http", "provider_usage", "providers", "tools", "worker")
MIGRATIONS = ("001_initial", "002_source_page_assets", "003_export_deletion_lifecycle",
              "004_maintenance_gate", "005_review_requests", "006_agent_budget_started_at",
              "007_manual_mistakes_and_office_text", "008_provider_usage", "009_browser_sessions")
PATHS = (
    "Dockerfile.learning", "requirements-learning.txt", "docs/contracts/openapi-v1.json",
    "docs/releases/README.md", "docs/releases/production-config.template.env",
    "docs/PROVIDER_CONFIGURATION.md", "docs/OPEN_WEBUI_TOOLS_INTEGRATION.md",
    "scripts/prepare_learning_release.py",
    *(f"learning_service/{name}.py" for name in MODULES),
    *(f"learning_service/migrations/{name}.sql" for name in MIGRATIONS),
)
LEGACY_PATHS = PATHS  # Frozen schema-9 profile; existing candidates still verify.
PATHS = (*LEGACY_PATHS,
         "learning_service/gateway_http.py", "learning_service/login_gateway.py",
         "learning_service/identity_admin.py", "learning_service/learner_context.py",
         "learning_service/migrations/010_session_identity_and_context.sql",
         "scripts/manage_learning_identities.py")

SCHEMA10_PATHS = PATHS
PATHS = (*SCHEMA10_PATHS, "learning_service/variant_review.py",
         "learning_service/migrations/011_variant_review_publication.sql",
         "docs/open-webui-reuse/learning-coach.template.json")

SCHEMA11_PATHS = PATHS
REUSE_PROFILE = "reuse-runtime-v1"
PATHS = (*SCHEMA11_PATHS, "learning_service/secret_files.py", "learning_service/operations.py",
         "deploy/open-webui-reuse/Dockerfile", "deploy/open-webui-reuse/requirements.lock",
         "deploy/open-webui-reuse/compose.learning-sidecar.yml", "deploy/open-webui-reuse/nginx.learning.conf",
         "deploy/open-webui-reuse/runtime.template.env", "scripts/check_reuse_compose.py",
         "scripts/reconnect_learning_network.py", "scripts/build_learning_candidate.py",
         "scripts/probe_reuse_runtime.py", "scripts/reuse_runtime_http_probe.py")
PRE_TEXTBOOK_PATHS = PATHS
PRE_TEXTBOOK_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-textbooks-v1"
PATHS = (*PRE_TEXTBOOK_PATHS, "learning_service/textbooks.py", "learning_service/textbook_quality.py")
TEXTBOOK_PATHS = PATHS
TEXTBOOK_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-practice-v1"
PATHS = (*TEXTBOOK_PATHS, "learning_service/practice.py", "learning_service/data/family_word_problems_v1.json",
         "learning_service/data/NOTICE.md", "learning_service/data/cn-math-taxonomy-LICENSE.txt",
         "scripts/import_family_practice.py")
PRACTICE_PATHS = PATHS
PRACTICE_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-math-references-v1"
PATHS = (*PRACTICE_PATHS, "learning_service/math_references.py", "learning_service/data/family_concepts_v1.json",
         "learning_service/data/faststudy-LICENSE-DATA.txt", "learning_service/data/faststudy-NOTICE.txt",
         "scripts/prepare_family_math_references.py", "docs/open-webui-reuse/math-references-integration.md",
         "learning_service/study_support.py", "docs/open-webui-reuse/scenarios-adoption.md",
         "scripts/prepare_study_support_examples.py", "scripts/probe_math_reference_native.py",
         "scripts/prepare_family_math.py")
MATH_REFERENCE_PATHS = PATHS
MATH_REFERENCE_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-study-workbench-v1"
PATHS = (*MATH_REFERENCE_PATHS, "learning_service/study_ui.py", "scripts/probe_study_candidate.py")

STUDY_WORKBENCH_PATHS = PATHS
STUDY_WORKBENCH_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-textbook-passages-v1"
PATHS = (*STUDY_WORKBENCH_PATHS, "learning_service/passage_evidence.py",
         "learning_service/passage_retrieval.py", "learning_service/textbook_passages.py",
         "deploy/open-webui-reuse/readonly_study_tools.py", "deploy/open-webui-reuse/main-study/family-bridge.js",
         "docs/open-webui-reuse/textbook-passages-runtime.md")

PASSAGE_RUNTIME_PATHS = PATHS
PASSAGE_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-practice-reserve-v1"
PATHS = (*PASSAGE_RUNTIME_PATHS, "learning_service/reserve_practice.py",
         "learning_service/data/family_reserve_practice_v1.json",
         "learning_service/data/family_chapter_coverage_v1.json",
         "scripts/prepare_reserve_practice.py", "docs/open-webui-reuse/practice-reserve.md")

RESERVE_RUNTIME_PATHS = PATHS
RESERVE_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-practice-collection-v1"
PATHS = (*RESERVE_RUNTIME_PATHS, "learning_service/migrations/012_practice_collection.sql",
         "docs/open-webui-reuse/practice-collection.md")

COLLECTION_RUNTIME_PATHS = PATHS
COLLECTION_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-practice-recovery-v1"
PATHS = (*COLLECTION_RUNTIME_PATHS, "learning_service/migrations/013_practice_recovery.sql",
         "docs/open-webui-reuse/practice-recovery.md")

RECOVERY_RUNTIME_PATHS = PATHS
RECOVERY_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-verified-backup-v1"
PATHS = (*RECOVERY_RUNTIME_PATHS, "docs/open-webui-reuse/backup-recovery.md")

BACKUP_RUNTIME_PATHS = PATHS
BACKUP_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-evidence-modules-v1"
PATHS = (*BACKUP_RUNTIME_PATHS, "learning_service/api_types.py", "learning_service/evidence_contracts.py",
         "learning_service/study_reference.py", "learning_service/study_routes.py",
         "docs/open-webui-reuse/evidence-modules.md")

EVIDENCE_RUNTIME_PATHS = PATHS
EVIDENCE_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-study-performance-v1"
PATHS = (*EVIDENCE_RUNTIME_PATHS, "learning_service/textbook_cache.py",
         "learning_service/study_deadline.py", "learning_service/study_cancellation.py",
         "docs/open-webui-reuse/study-performance.md")

PERFORMANCE_RUNTIME_PATHS = PATHS
PERFORMANCE_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-study-read-connections-v1"
PATHS = (*PERFORMANCE_RUNTIME_PATHS, "learning_service/study_read_db.py",
         "docs/open-webui-reuse/study-read-latency.md")

READ_CONNECTION_RUNTIME_PATHS = PATHS
READ_CONNECTION_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-study-read-scheduling-v1"
PATHS = (*READ_CONNECTION_RUNTIME_PATHS, "docs/open-webui-reuse/study-read-scheduling.md")

READ_SCHEDULING_RUNTIME_PATHS = PATHS
READ_SCHEDULING_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-study-host-compatibility-v1"
PATHS = (*READ_SCHEDULING_RUNTIME_PATHS, "docs/open-webui-reuse/host-compatibility.md")

HOST_RUNTIME_PATHS = PATHS
HOST_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-chapter-practice-v1"
PATHS = (*HOST_RUNTIME_PATHS, "learning_service/chapter_practice.py",
         "learning_service/data/family_chapter_math_v1.json",
         "learning_service/data/family_chapter_upper_v1.json",
         "learning_service/data/family_chapter_remaining_v1.json",
         "scripts/import_chapter_practice.py", "scripts/prepare_chapter_practice.py",
         "docs/open-webui-reuse/chapter-practice.md", "learning_service/practice_coverage.py",
         "learning_service/data/family_math_coverage_plan_v1.json")

CHAPTER_RUNTIME_PATHS = PATHS
CHAPTER_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-math-knowledge-v2"
PATHS = (*CHAPTER_RUNTIME_PATHS, "learning_service/data/family_chapter_math_g2_depth_v1.json",
         "learning_service/data/family_math_coverage_plan_v2.json")

MATH_V2_RUNTIME_PATHS = PATHS
MATH_V2_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-math-knowledge-v3"
PATHS = (*MATH_V2_RUNTIME_PATHS, "learning_service/data/family_chapter_math_g7_depth_v1.json",
         "learning_service/data/family_math_coverage_plan_v3.json")

MATH_V3_RUNTIME_PATHS = PATHS
MATH_V3_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-math-challenge-v4"
PATHS = (*MATH_V3_RUNTIME_PATHS, "learning_service/data/family_chapter_math_g2_challenge_v1.json",
         "learning_service/data/family_math_coverage_plan_v4.json", "learning_service/practice_design.py")


MATH_V4_RUNTIME_PATHS = PATHS
MATH_V4_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-math-multistep-v5"
PATHS = (*MATH_V4_RUNTIME_PATHS, "learning_service/data/family_chapter_math_g2_multistep_v1.json",
         "learning_service/data/family_math_coverage_plan_v5.json", "learning_service/practice_response.py")

VARIETY_V5_RUNTIME_PATHS = PATHS
VARIETY_V5_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-other-textbooks-v6"
PATHS = (*VARIETY_V5_RUNTIME_PATHS, "learning_service/data/family_chapter_math_g7_multistep_v1.json",
         "learning_service/data/family_chapter_upper_variety_v1.json",
         "learning_service/data/family_chapter_remaining_variety_v1.json",
         "learning_service/data/family_math_coverage_plan_v6.json")

VARIETY_V6_RUNTIME_PATHS = PATHS
VARIETY_V6_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-subject-knowledge-v7"
PATHS = (*VARIETY_V6_RUNTIME_PATHS, "learning_service/subject_coverage.py",
         "learning_service/data/family_chapter_subject_knowledge_v1.json",
         "learning_service/data/family_subject_coverage_plan_v1.json")

SUBJECT_V7_RUNTIME_PATHS = PATHS
SUBJECT_V7_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-challenge-tier-v8"
PATHS = (*SUBJECT_V7_RUNTIME_PATHS, "learning_service/migrations/014_challenge_difficulty.sql",
         "learning_service/data/family_chapter_challenge_variety_v1.json",
         "learning_service/data/family_subject_coverage_plan_v2.json")

CHALLENGE_V8_RUNTIME_PATHS = PATHS
CHALLENGE_V8_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-knowledge-quality-v9"
PATHS = (*CHALLENGE_V8_RUNTIME_PATHS, "learning_service/data/family_subject_coverage_plan_v3.json")

QUALITY_V9_RUNTIME_PATHS = PATHS
QUALITY_V9_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-math-gaps-v10"
PATHS = (*QUALITY_V9_RUNTIME_PATHS, "learning_service/data/family_chapter_math_gaps_v1.json",
         "learning_service/data/family_subject_coverage_plan_v4.json")

MATH_GAPS_V10_RUNTIME_PATHS = PATHS
MATH_GAPS_V10_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-subject-gaps-v11"
PATHS = (*MATH_GAPS_V10_RUNTIME_PATHS, "learning_service/data/family_chapter_subject_gaps_v1.json",
         "learning_service/data/family_subject_coverage_plan_v5.json")

SUBJECT_GAPS_V11_RUNTIME_PATHS = PATHS
SUBJECT_GAPS_V11_RUNTIME_PROFILE = REUSE_PROFILE
REUSE_PROFILE = "reuse-runtime-textbook-completion-v12"
PATHS = (*SUBJECT_GAPS_V11_RUNTIME_PATHS, "learning_service/data/textbook_lower_reading_v1.json")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _source(root: Path, relative: str) -> Path:
    path = root / relative
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root)
            or not path.is_file() or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError("release source is missing, a symlink, or outside the root: " + relative)
    return path


def prepare(destination: Path, root: Path = ROOT) -> dict:
    root = root.resolve()
    destination = destination.absolute()
    if not destination.resolve().is_relative_to(root) or destination == root or destination.exists():
        raise ValueError("choose a new release directory under the project; existing files are preserved")
    # Read only named source files, never .env, data or P0 private configuration.
    payloads = {name: _source(root, name).read_bytes() for name in sorted(PATHS)}
    fingerprints = {name: sha256(data) for name, data in payloads.items()}
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in payloads.items():
                item = tarfile.TarInfo(name)
                item.size, item.mode, item.mtime = len(data), 0o644, 0
                archive.addfile(item, io.BytesIO(data))
    archive_bytes = stream.getvalue()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True)
    manifest = {
        "format": "dd-learning-source-candidate-v1",
        "state": "local_source_candidate_not_built_not_deployed",
        "git_head": head.stdout.strip() if head.returncode == 0 else None,
        "worktree_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
        "schema_revision": 14, "open_webui_target_version": "0.12.5",
        "source_profile": REUSE_PROFILE,
        "image_digest": None, "source_sha256": fingerprints,
        "source_set_sha256": sha256(_json(fingerprints)), "archive_sha256": sha256(archive_bytes),
        "authorization": {"production_cutover": "not_authorized", "paid_provider_calls": "not_authorized",
                          "real_student_data_export": "not_authorized", "continuous_trial": "not_started"},
        "verification_boundary": "source sealing only; no clean image build, runtime or real provider acceptance",
    }
    destination.mkdir(parents=True, mode=0o700)
    (destination / "source.tar.gz").write_bytes(archive_bytes)
    (destination / "manifest.json").write_bytes(_json(manifest))
    verify(destination)
    return manifest


def verify(destination: Path) -> dict:
    manifest = json.loads((destination / "manifest.json").read_text())
    paths = {9: LEGACY_PATHS, 10: SCHEMA10_PATHS, 11: SCHEMA11_PATHS}.get(manifest.get("schema_revision"))
    if manifest.get("source_profile") == REUSE_PROFILE and manifest.get("schema_revision") == 14:
        paths = PATHS
    elif manifest.get("source_profile") == SUBJECT_GAPS_V11_RUNTIME_PROFILE and manifest.get("schema_revision") == 14:
        paths = SUBJECT_GAPS_V11_RUNTIME_PATHS
    elif manifest.get("source_profile") == MATH_GAPS_V10_RUNTIME_PROFILE and manifest.get("schema_revision") == 14:
        paths = MATH_GAPS_V10_RUNTIME_PATHS
    elif manifest.get("source_profile") == QUALITY_V9_RUNTIME_PROFILE and manifest.get("schema_revision") == 14:
        paths = QUALITY_V9_RUNTIME_PATHS
    elif manifest.get("source_profile") == CHALLENGE_V8_RUNTIME_PROFILE and manifest.get("schema_revision") == 14:
        paths = CHALLENGE_V8_RUNTIME_PATHS
    elif manifest.get("source_profile") == SUBJECT_V7_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = SUBJECT_V7_RUNTIME_PATHS
    elif manifest.get("source_profile") == VARIETY_V6_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = VARIETY_V6_RUNTIME_PATHS
    elif manifest.get("source_profile") == VARIETY_V5_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = VARIETY_V5_RUNTIME_PATHS
    elif manifest.get("source_profile") == MATH_V4_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = MATH_V4_RUNTIME_PATHS
    elif manifest.get("source_profile") == MATH_V3_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = MATH_V3_RUNTIME_PATHS
    elif manifest.get("source_profile") == MATH_V2_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = MATH_V2_RUNTIME_PATHS
    elif manifest.get("source_profile") == CHAPTER_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = CHAPTER_RUNTIME_PATHS
    elif manifest.get("source_profile") == HOST_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = HOST_RUNTIME_PATHS
    elif manifest.get("source_profile") == READ_SCHEDULING_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = READ_SCHEDULING_RUNTIME_PATHS
    elif manifest.get("source_profile") == READ_CONNECTION_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = READ_CONNECTION_RUNTIME_PATHS
    elif manifest.get("source_profile") == PERFORMANCE_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = PERFORMANCE_RUNTIME_PATHS
    elif manifest.get("source_profile") == EVIDENCE_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = EVIDENCE_RUNTIME_PATHS
    elif manifest.get("source_profile") == BACKUP_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = BACKUP_RUNTIME_PATHS
    elif manifest.get("source_profile") == RECOVERY_RUNTIME_PROFILE and manifest.get("schema_revision") == 13:
        paths = RECOVERY_RUNTIME_PATHS
    elif manifest.get("source_profile") == COLLECTION_RUNTIME_PROFILE and manifest.get("schema_revision") == 12:
        paths = COLLECTION_RUNTIME_PATHS
    elif manifest.get("source_profile") == RESERVE_RUNTIME_PROFILE and manifest.get("schema_revision") == 11:
        paths = RESERVE_RUNTIME_PATHS
    elif manifest.get("source_profile") == PASSAGE_RUNTIME_PROFILE and manifest.get("schema_revision") == 11:
        paths = PASSAGE_RUNTIME_PATHS
    elif manifest.get("source_profile") == STUDY_WORKBENCH_PROFILE and manifest.get("schema_revision") == 11:
        paths = STUDY_WORKBENCH_PATHS
    elif manifest.get("source_profile") == MATH_REFERENCE_PROFILE and manifest.get("schema_revision") == 11:
        paths = MATH_REFERENCE_PATHS
    elif manifest.get("source_profile") == PRACTICE_PROFILE and manifest.get("schema_revision") == 11:
        paths = PRACTICE_PATHS
    elif manifest.get("source_profile") == TEXTBOOK_PROFILE and manifest.get("schema_revision") == 11:
        paths = TEXTBOOK_PATHS
    elif manifest.get("source_profile") == PRE_TEXTBOOK_PROFILE and manifest.get("schema_revision") == 11:
        paths = PRE_TEXTBOOK_PATHS
    elif manifest.get("source_profile"):
        raise ValueError("unknown source profile")
    if not paths or manifest.get("format") != "dd-learning-source-candidate-v1" or set(manifest["source_sha256"]) != set(paths):
        raise ValueError("invalid source manifest")
    if manifest["state"] != "local_source_candidate_not_built_not_deployed" or manifest["image_digest"] is not None:
        raise ValueError("invalid release boundary")
    archive_bytes = (destination / "source.tar.gz").read_bytes()
    if sha256(archive_bytes) != manifest["archive_sha256"]:
        raise ValueError("source archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        members = archive.getmembers()
        if (len(members) != len(paths) or {m.name for m in members} != set(paths)
                or any(not m.isfile() or m.size > 2 * 1024 * 1024 for m in members)):
            raise ValueError("source archive file set mismatch")
        for member in members:
            if sha256(archive.extractfile(member).read()) != manifest["source_sha256"][member.name]:
                raise ValueError("source member checksum mismatch: " + member.name)
    if sha256(_json(manifest["source_sha256"])) != manifest["source_set_sha256"]:
        raise ValueError("source set checksum mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.destination) if args.action == "prepare" else verify(args.destination)
    print(json.dumps({"state": manifest["state"], "schema_revision": manifest["schema_revision"],
                      "source_files": len(manifest["source_sha256"]), "source_set_sha256": manifest["source_set_sha256"],
                      "archive_sha256": manifest["archive_sha256"], "image_digest": manifest["image_digest"]}))


if __name__ == "__main__":
    main()
