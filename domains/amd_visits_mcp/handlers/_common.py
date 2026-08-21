"""Shared helpers for amd-visits-mcp handlers."""
from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Any, Callable

from amd_mcp_common.action_guard import maybe_guarded


# Client factory - server.py wires this at boot.
_client_factory: Callable[[], Any] | None = None


def set_client_factory(factory: Callable[[], Any]) -> None:
    global _client_factory
    _client_factory = factory


def get_client():
    if _client_factory is None:
        raise RuntimeError(
            "amd-visits-mcp: handlers._common has no AMDClient factory. "
            "server.build_server(...) must call set_client_factory()."
        )
    return maybe_guarded(_client_factory())


def serialize(obj) -> Any:
    """Recursive dataclass+datetime+lxml.Element serializer."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return serialize(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # lxml.Element duck-typing.
    if hasattr(obj, "tag") and hasattr(obj, "attrib"):
        return raw_to_dict(obj)
    return obj


def raw_to_dict(node) -> Any:
    """lxml.Element -> JSON-friendly dict (tag/attrs/children/text).

    Mirrors the legacy server's helper. Redaction happens later in
    wrap_tool's pipeline.
    """
    if node is None:
        return None
    if not hasattr(node, "tag"):
        return str(node)
    out: dict[str, Any] = {"_tag": node.tag, "_attrs": dict(node.attrib)}
    children = list(node)
    if children:
        out["_children"] = [raw_to_dict(c) for c in children]
    text = (node.text or "").strip() if node.text else ""
    if text:
        out["_text"] = text
    return out


def summarize_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    """Group rows by a single string field, skip empty values.

    Shared across visits handlers (getdatevisits / getupdatedvisits /
    getreminderrecallvisits) because the grouping shape is identical
    even when sort keys and extracted fields differ.
    """
    out: dict[str, int] = {}
    for r in rows:
        k = (r.get(key) or "").strip()
        if not k:
            continue
        out[k] = out.get(k, 0) + 1
    return out
