"""Shared helpers for amd-providers-mcp handlers."""
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
            "amd-providers-mcp: handlers._common has no AMDClient factory. "
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


def summarize_by(rows: list[dict], key: str) -> dict[str, int]:
    """Group rows by a single string field, skip empty values."""
    out: dict[str, int] = {}
    for r in rows:
        k = (r.get(key) or "").strip()
        if not k:
            continue
        out[k] = out.get(k, 0) + 1
    return out


def extract_rows_by_tag(raw_dict: Any, tag: str) -> list[dict]:
    """Walk the raw_to_dict tree and pull all <tag> elements out.

    Returns each match's attrs flattened with `_child_text` and
    `_child_attrs` nested dicts so handlers can read both attribute-
    style and child-element-style fields cleanly.
    """
    out: list[dict] = []
    if not isinstance(raw_dict, dict):
        return out

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("_tag") == tag:
            attrs = dict(node.get("_attrs") or {})
            child_text: dict[str, str] = {}
            child_attrs: dict[str, dict[str, str]] = {}
            for child in node.get("_children") or []:
                if not isinstance(child, dict):
                    continue
                ctag = child.get("_tag")
                ctext = child.get("_text")
                if ctag and ctext:
                    child_text[ctag] = ctext
                if ctag and child.get("_attrs"):
                    child_attrs[ctag] = dict(child.get("_attrs"))
            attrs["_child_text"] = child_text
            attrs["_child_attrs"] = child_attrs
            out.append(attrs)
            return
        for child in node.get("_children") or []:
            _walk(child)

    _walk(raw_dict)
    return out
