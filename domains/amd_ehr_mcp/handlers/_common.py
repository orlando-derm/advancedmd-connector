"""Shared helpers for amd-ehr-mcp handlers."""
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
            "amd-ehr-mcp: handlers._common has no AMDClient factory. "
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


def extract_rows_by_tag(raw_dict: Any, tag: str) -> list[dict]:
    """Walk the raw_to_dict tree and pull all <tag> elements out."""
    out: list[dict] = []
    if not isinstance(raw_dict, dict):
        return out

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("_tag") == tag:
            attrs = dict(node.get("_attrs") or {})
            out.append(attrs)
            return
        for child in node.get("_children") or []:
            _walk(child)

    _walk(raw_dict)
    return out


def count_rows_for_tags(raw_dict: Any, *tags: str) -> int:
    """Sum counts across multiple candidate row tags.

    EHR endpoints vary in tag naming (allergy/medication/problem/etc.);
    we pass a tuple and take the FIRST non-zero match, mirroring the
    fallback pattern used in patients-mcp.getreminderappts.
    """
    for tag in tags:
        rows = extract_rows_by_tag(raw_dict, tag)
        if rows:
            return len(rows)
    return 0
