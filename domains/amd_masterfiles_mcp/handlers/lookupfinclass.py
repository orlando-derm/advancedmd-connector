"""amd_masterfiles_lookup_finclass — capped matches, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import capped_match_response, get_client, raw_to_dict

ACTION = "lookupfinclass"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupfinclass",)


def _flatten(row: dict) -> dict[str, str]:
    return {
        "finclass_id": row.get("id", ""),
        "name": row.get("name", ""),
        "code": row.get("code", ""),
    }


async def handle(*, query: str) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupfinclass takes `name=` on the wire (docx sample line
    # 5849: <ppmdmsg action="lookupfinclass" ... name="m" page="1" />).
    # Adam-facing arg stays `query`.
    call_kwargs: dict[str, Any] = {"name": query}
    raw_dict, err = safe_amd_call(client, action="lookupfinclass", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    return capped_match_response(
        raw_dict, row_tag="finclass", query=query, flatten=_flatten,
        sort_key=lambda m: ((m.get("name") or "").lower(), m.get("finclass_id") or ""),
    )
