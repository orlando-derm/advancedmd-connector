"""amd_masterfiles_lookup_zipcode — capped matches, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import capped_match_response, get_client, raw_to_dict

ACTION = "lookupzipcode"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupzipcode",)


def _flatten(row: dict) -> dict[str, str]:
    return {
        "zipcode_id": row.get("id", ""),
        "zip": row.get("code", "") or row.get("zip", ""),
        "city": row.get("city", "") or row.get("name", ""),
        "state": row.get("state", ""),
    }


async def handle(*, query: str) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupzipcode takes `name=` for City/State criterion or
    # `code=` for the ZIP digits (docx Lookup Criteria table lines
    # 5713-5723; both `name` and `code` columns marked X; docx 5772
    # explains `name` represents City for zipcode lookups). Adam's
    # query string is free-text — pass as `name=` (the broader
    # criterion). Adam-facing arg stays `query`.
    call_kwargs: dict[str, Any] = {"name": query}
    raw_dict, err = safe_amd_call(client, action="lookupzipcode", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    return capped_match_response(
        raw_dict, row_tag="zipcode", query=query, flatten=_flatten,
        sort_key=lambda m: (m.get("zip") or "", (m.get("city") or "").lower()),
    )
