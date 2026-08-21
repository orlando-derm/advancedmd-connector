"""amd_patients_lookup_resp_party — AMD lookuprespparty action.

Returns capped match list + cardinality (Aaron 2026-06-04: "it cannot
do any math or aggregations properly"). No raw AMD blob.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "lookuprespparty"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookuprespparty",)


def _flatten_match(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "respparty_id": row.get("id", "") or child_text.get("id", ""),
        "first_name": row.get("first_name", "") or child_text.get("first_name", ""),
        "last_name": row.get("last_name", "") or child_text.get("last_name", ""),
        "name": row.get("name", "") or child_text.get("name", ""),
    }


async def handle(*, query: str) -> dict[str, Any]:
    client = get_client()
    # AMD's lookuprespparty takes `name=` on the wire (docx sample line
    # 5840: <ppmdmsg action="lookuprespparty" class="api" ...
    #          name="a,a" page="1" />).
    # Adam-facing arg stays `query`.
    call_kwargs: dict[str, Any] = {"name": query}
    raw_dict, err = safe_amd_call(client, action="lookuprespparty", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    raw_rows = extract_rows_by_tag(raw_dict, "respparty")
    matches = [_flatten_match(r) for r in raw_rows]
    matches.sort(key=lambda m: ((m.get("last_name") or "").lower(), (m.get("first_name") or "").lower(), m.get("respparty_id") or ""))
    _MATCH_CAP = 5
    total = len(matches)
    return {
        "query": query,
        "count": total,
        "matches": matches[:_MATCH_CAP],
        "narrow_query": total > _MATCH_CAP,
    }
