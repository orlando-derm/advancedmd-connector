"""Shared helpers for amd-system-mcp handlers."""
from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Any, Callable

from amd_mcp_common.action_guard import maybe_guarded


_client_factory: Callable[[], Any] | None = None


def set_client_factory(factory: Callable[[], Any]) -> None:
    global _client_factory
    _client_factory = factory


def get_client():
    if _client_factory is None:
        raise RuntimeError(
            "amd-system-mcp: handlers._common has no AMDClient factory. "
            "server.build_server(...) must call set_client_factory()."
        )
    return maybe_guarded(_client_factory())


def serialize(obj) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return serialize(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "tag") and hasattr(obj, "attrib"):
        return raw_to_dict(obj)
    return obj


def raw_to_dict(node) -> Any:
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
