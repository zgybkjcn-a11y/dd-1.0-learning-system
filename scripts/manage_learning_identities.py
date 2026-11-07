#!/usr/bin/env python3
"""Validate/plan/apply an explicit Learning identity manifest, never WebUI data."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.identity_admin import IdentityPlanError, apply_identity, plan_identity, validate_manifest
from learning_service.login_gateway import strict_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("validate", "plan", "apply"))
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--database", type=Path)
    p.add_argument("--operator")
    p.add_argument("--reviewed-plan-sha256")
    a = p.parse_args()
    try:
        if a.manifest.stat().st_size > 1024 * 1024:
            raise IdentityPlanError("manifest exceeds 1 MiB")
        manifest = validate_manifest(strict_json(a.manifest.read_bytes()))
        if a.action == "validate":
            result = {"status": "valid", "database_opened": False}
        else:
            if not a.database or not a.operator or a.action == "apply" and not a.reviewed_plan_sha256:
                raise IdentityPlanError("database/operator required; apply additionally requires the reviewed plan hash")
            result = plan_identity(manifest, a.database, a.operator) if a.action == "plan" else apply_identity(manifest, a.database, a.operator, a.reviewed_plan_sha256)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        # Do not print manifest/SQLite data or tokens in generic failures.
        p.exit(2, (str(exc) if isinstance(exc, IdentityPlanError) else "identity input or database operation failed") + "\n")


if __name__ == "__main__":
    main()
