"""amd_providers_lookup_ref_provider — AMD lookuprefprovider action.

Returns capped match list + cardinality (Aaron 2026-06-04: "it cannot
do any math or aggregations properly"). No raw AMD blob.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "lookuprefprovider"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookuprefprovider",)


def _flatten_match(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "refprovider_id": row.get("id", "") or child_text.get("id", ""),
        "name": row.get("name", "") or child_text.get("name", ""),
        "code": row.get("code", ""),
        "specialty": row.get("specialty", ""),
        "practicename": row.get("practicename", ""),
    }


async def handle(*, query: str) -> dict[str, Any]:
    client = get_client()
    # AMD's lookuprefprovider takes `name=` on the wire (docx Lookup
    # Criteria table line 5680-5690: `name` and `code` and `specialty`
    # columns marked X). Adam-facing arg stays `query`.
    call_kwargs: dict[str, Any] = {"name": query}
    raw_dict, err = safe_amd_call(client, action="lookuprefprovider", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    raw_rows = extract_rows_by_tag(raw_dict, "refprovider")
    matches = [_flatten_match(r) for r in raw_rows]
    matches.sort(key=lambda m: ((m.get("name") or "").lower(), m.get("refprovider_id") or ""))
    # Cap matches at 5 + narrow_query flag. Mirror lookup_patient.py
    # pattern: Adam is for id resolution, not enumeration.
    _MATCH_CAP = 5
    total = len(matches)
    return {
        "query": query,
        "count": total,
        "matches": matches[:_MATCH_CAP],
        "narrow_query": total > _MATCH_CAP,
    }
