"""Small, isolated facsimile of the Open WebUI Tools loading contract.

This module intentionally lives under tests.  It must never become a runtime
dependency of the learning service or access the installed Open WebUI data.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import types
from pathlib import Path
from typing import Any


def load_tool_module(source_path: Path, tool_id: str = "dd-learning-test") -> tuple[types.ModuleType, object]:
    """Load a Tools source file the way Open WebUI executes workspace tools."""
    module = types.ModuleType(f"tool_{tool_id}")
    module.__file__ = str(source_path)
    source = source_path.read_text(encoding="utf-8")
    exec(compile(source, str(source_path), "exec"), module.__dict__)  # noqa: S102 - isolated compatibility test
    if not hasattr(module, "Tools"):
        raise AssertionError("tool module has no Tools class")
    return module, module.Tools()


def parse_tool_metadata(source_path: Path) -> dict[str, str]:
    """Parse the scalar metadata fields Open WebUI reads from a Tool docstring."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    docstring = ast.get_docstring(tree, clean=False) or ""
    fields = {"title", "author", "description", "required_open_webui_version", "version"}
    metadata: dict[str, str] = {}
    for line in docstring.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in fields:
            metadata[key.strip()] = value.strip()
    return metadata


def inject_valves(tool: object, values: dict[str, Any]) -> None:
    """Apply the instance-level valve replacement used by Open WebUI."""
    if not hasattr(tool, "valves") or not hasattr(tool, "Valves"):
        raise AssertionError("tool does not expose an injectable Valves instance")
    tool.valves = tool.Valves(**values)  # type: ignore[attr-defined]


def discover_functions(tool: object) -> dict[str, Any]:
    """Match Open WebUI's public callable discovery and class filtering."""
    return {
        name: getattr(tool, name)
        for name in dir(tool)
        if callable(getattr(tool, name))
        and not name.startswith("_")
        and not inspect.isclass(getattr(tool, name))
    }


def visible_parameters(function: Any) -> set[str]:
    """Return parameters that a model would see after reserved injection."""
    return {name for name in inspect.signature(function).parameters if not name.startswith("__")}


def call_tool(tool: object, name: str, model_arguments: dict[str, Any], user: dict[str, Any]) -> Any:
    """Invoke a discovered function with host-owned reserved context.

    Model arguments beginning with ``__`` are discarded.  The host injects its
    own ``__user__`` object only when the function declares that parameter.
    """
    return asyncio.run(call_tool_async(tool, name, model_arguments, user))


async def call_tool_async(
    tool: object,
    name: str,
    model_arguments: dict[str, Any],
    user: dict[str, Any],
    event_call: Any = None,
) -> Any:
    """Async form used by native Open WebUI Tools with ``__event_call__``."""
    function = discover_functions(tool).get(name)
    if function is None:
        raise AssertionError(f"unknown tool function: {name}")
    parameters = inspect.signature(function).parameters
    visible = visible_parameters(function)
    supplied = {key: value for key, value in model_arguments.items() if not key.startswith("__")}
    unknown = set(supplied) - visible
    if unknown:
        raise AssertionError(f"model supplied unknown parameters: {sorted(unknown)}")
    if "__user__" in parameters:
        supplied["__user__"] = user
    if "__event_call__" in parameters:
        supplied["__event_call__"] = event_call
    result = function(**supplied)
    if inspect.isawaitable(result):
        result = await result
    return result
