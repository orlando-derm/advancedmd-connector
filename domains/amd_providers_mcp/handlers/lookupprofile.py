"""amd_providers_lookup_profile — AMD lookupprofile action.

Returns capped match list + cardinality (Aaron 2026-06-04: "it cannot
do any math or aggregations properly"). No raw AMD blob.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "lookupprofile"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupprofile",)


def _flatten_match(row: dict) -> dict[str, str]:
    return {
        "profile_id": row.get("id", ""),
        "name": row.get("name", ""),
        "code": row.get("code", ""),
    }


async def handle(*, query: str) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupprofile takes `name=` on the wire (docx sample line
    # 5843: <ppmdmsg action="lookupprofile" class="api" ...
    #          name="" page="1" />). Adam-facing arg stays `query`.
    call_kwargs: dict[str, Any] = {"name": query}
    raw_dict, err = safe_amd_call(client, action="lookupprofile", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    raw_rows = extract_rows_by_tag(raw_dict, "profile")
    matches = [_flatten_match(r) for r in raw_rows]
    matches.sort(key=lambda m: ((m.get("name") or "").lower(), m.get("profile_id") or ""))
    _MATCH_CAP = 5
    total = len(matches)
    return {
        "query": query,
        "count": total,
        "matches": matches[:_MATCH_CAP],
        "narrow_query": total > _MATCH_CAP,
    }
