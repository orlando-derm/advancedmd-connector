"""Shared helpers for amd-codes-mcp handlers."""
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
            "amd-codes-mcp: handlers._common has no AMDClient factory. "
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


def _build_lookup_handler(row_tag: str):
    """Factory: returns an async `handle(*, query)` that performs the
    standard codes-domain lookup enrichment for a given row tag.

    Each AMD codes lookup returns a list of `<row_tag>` elements with
    `id`, `code`, `name` attributes. The enrichment shape is the same
    across cpt/icd10/hcpcs/modcode: `{query, count, matches, raw}`.

    Sort key: `code` ascending (the natural scan order for staff).
    """
    async def handle(*, query: str, _client_class: str, _action: str) -> dict[str, Any]:
        if not query:
            return {"error": "bad_input", "details": {"reason": "query required"}}
        client = get_client()
        # Use the call signature passed in by the wrapper (each handler
        # may need its own class_/codeset). AMD's wire attribute for the
        # search criterion on action="lookup" is `search=`, not `query=`
        # (see lookup_cpt.py for the canonical reference + legacy
        # amd-mcp-server/tools/lookups.py:99).
        raw = client.call(action="lookup", class_=_client_class, search=query)
        raw_dict = raw_to_dict(raw)
        matches = extract_rows_by_tag(raw_dict, row_tag)
        # Flatten + sort by code asc.
        flat = [
            {
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "id": r.get("id", ""),
            }
            for r in matches
        ]
        flat.sort(key=lambda m: (m.get("code") or "", m.get("id") or ""))
        _CAP = 5
        return {
            "query": query,
            "count": len(flat),
            "matches": flat[:_CAP],
            "narrow_query": len(flat) > _CAP,
        }

    return handle


def enriched_codes_response(raw_dict: Any, *, row_tag: str, query: str) -> dict[str, Any]:
    """Build the canonical `{query, count, matches, raw}` envelope.

    Used by each codes-domain handler so the codeset-specific call
    signature stays handler-local while the shape stays uniform.
    """
    matches = extract_rows_by_tag(raw_dict, row_tag)
    flat = [
        {
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "id": r.get("id", ""),
        }
        for r in matches
    ]
    flat.sort(key=lambda m: (m.get("code") or "", m.get("id") or ""))
    # Cap matches at 5. Adam reads `count` for cardinality and the (at
    # most 5) matches for code+name pairs. If `narrow_query` is true the
    # user should refine instead of receiving a long list to count.
    # Aaron 2026-06-04: "it cannot do any math or aggregations properly."
    _CAP = 5
    return {
        "query": query,
        "count": len(flat),
        "matches": flat[:_CAP],
        "narrow_query": len(flat) > _CAP,
    }
