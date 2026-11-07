#!/usr/bin/env python3
"""Plan a reviewed reconnect; default read-only, never change a default network."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess


def read_metadata(container: str, network: str) -> tuple[dict, dict]:
    def get(args):
        r = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=15)
        if r.returncode:
            raise ValueError("Docker metadata is unavailable")
        return json.loads(r.stdout)
    c = get(["inspect", "--format", '{"id":{{json .Id}},"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}}}', container])
    n = get(["network", "inspect", "--format", '{"id":{{json .Id}},"name":{{json .Name}},"internal":{{json .Internal}},"labels":{{json .Labels}}}', network])
    return c, n


def plan(container: dict, network: dict, project: str, operator: str) -> dict:
    if not re.fullmatch(r"dd-learning-[a-z0-9-]{1,80}", project) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", operator):
        raise ValueError("explicit dedicated project and operator required")
    c_labels, n_labels = container.get("labels") or {}, network.get("labels") or {}
    if c_labels.get("com.docker.compose.service") != "open-webui" or c_labels.get("com.docker.compose.project") != "open-webui":
        raise ValueError("unexpected WebUI installation")
    if (network.get("internal") is not True or n_labels.get("com.docker.compose.project") != project
            or n_labels.get("com.docker.compose.network") != "learning-internal"):
        raise ValueError("unexpected target network")
    if "open-webui_default" not in container.get("networks", {}):
        raise ValueError("original WebUI network is missing")
    result = {"container_id":container["id"], "network_id":network["id"], "network_name":network["name"],
              "original_networks": sorted(container["networks"]), "project":project, "operator":operator,
              "action":"already_connected" if network["name"] in container["networks"] else "connect_internal_network"}
    result["plan_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--network", required=True); p.add_argument("--project", required=True)
    p.add_argument("--operator", required=True); p.add_argument("--apply-plan-sha256")
    args = p.parse_args()
    c, n = read_metadata("open-webui", args.network)
    result = plan(c, n, args.project, args.operator)
    if args.apply_plan_sha256:
        if args.apply_plan_sha256 != result["plan_sha256"]:
            raise ValueError("reviewed plan is stale")
        if result["action"] == "connect_internal_network":
            # This is a future W13 production action, never used by local probes.
            r = subprocess.run(["docker", "network", "connect", n["id"], c["id"]], capture_output=True, timeout=15)
            if r.returncode:
                raise ValueError("network reconnect failed")
        current, target = read_metadata("open-webui", args.network)
        if current["id"] != c["id"] or target["name"] not in current["networks"] or not set(c["networks"]).issubset(current["networks"]):
            raise ValueError("reconnect verification failed")
        result["applied"] = True
    else:
        result["applied"] = False
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
