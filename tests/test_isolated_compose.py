from __future__ import annotations

from copy import deepcopy

from scripts.check_isolated_compose import ROOT, validate_compose_config


def safe_compose_config():
    service = {
        "image": "dd-learning:local",
        "networks": {"learning-internal": None},
        "volumes": [
            {
                "type": "volume",
                "source": "dd_learning_data",
                "target": "/var/lib/dd-learning",
            }
        ],
        "environment": {
            "LEARNING_DEV_MODE": "0",
            "LEARNING_DOCUMENT_PROVIDER": "mock-document-v1",
            "LEARNING_DIAGNOSIS_PROVIDER": "mock-diagnosis-v1",
            "LEARNING_VARIANT_PROVIDER": "mock-variant-v1",
        },
    }
    return {
        "services": {
            "learning-api": {
                **deepcopy(service),
                "build": {"context": str(ROOT), "dockerfile": "Dockerfile.learning"},
            },
            "learning-worker": deepcopy(service),
        },
        "networks": {"learning-internal": {"internal": True}},
        "volumes": {"dd_learning_data": {"name": "isolated_dd_learning_data"}},
    }


def test_isolated_compose_config_passes():
    assert validate_compose_config(safe_compose_config()) == []


def test_isolated_compose_rejects_host_ports():
    config = safe_compose_config()
    config["services"]["learning-api"]["ports"] = ["31010:31010"]
    assert "learning-api must not publish host ports" in validate_compose_config(config)


def test_isolated_compose_rejects_host_mounts():
    config = safe_compose_config()
    config["services"]["learning-api"]["volumes"] = [
        {"type": "bind", "source": "/srv/production/data", "target": "/var/lib/dd-learning"}
    ]
    assert "learning-api must use only the managed dd_learning_data volume" in validate_compose_config(config)


def test_isolated_compose_rejects_external_network_and_provider():
    config = safe_compose_config()
    config["networks"]["learning-internal"]["internal"] = False
    config["services"]["learning-worker"]["environment"]["LEARNING_DOCUMENT_PROVIDER"] = "external-provider"
    errors = validate_compose_config(config)
    assert "learning-internal must be an isolated, non-external network" in errors
    assert "learning-worker must use the deterministic LEARNING_DOCUMENT_PROVIDER provider" in errors


def test_isolated_compose_rejects_development_mode():
    config = safe_compose_config()
    config["services"]["learning-api"]["environment"]["LEARNING_DEV_MODE"] = "1"
    errors = validate_compose_config(config)
    assert "learning-api must run with development mode disabled" in errors


def test_isolated_compose_rejects_extra_services():
    config = safe_compose_config()
    config["services"]["unexpected"] = {}
    assert validate_compose_config(config) == ["service set must contain only learning-api and learning-worker"]
