"""amd_masterfiles_lookup_note_types — capped matches, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import capped_match_response, get_client, raw_to_dict

ACTION = "lookupnotetypes"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupnotetypes",)


def _flatten(row: dict) -> dict[str, str]:
    return {
        "notetype_id": row.get("id", ""),
        "name": row.get("name", ""),
        "code": row.get("code", ""),
    }


async def handle(*, query: str) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupnotetypes per the docx Lookup Criteria table (lines
    # 5724-5733) only marks the `code` column for this action — `name`
    # is NOT a listed criterion. Pass query as `code=` to match.
    # [AARON-REVIEWABLE-DRIFT-2] No live working example exists for
    # this action; `code=` is the docx table reading. If live testing
    # shows AMD also accepts `name=` (it does for most siblings), this
    # may be safely widened.
    call_kwargs: dict[str, Any] = {"code": query}
    raw_dict, err = safe_amd_call(client, action="lookupnotetypes", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    return capped_match_response(
        raw_dict, row_tag="notetype", query=query, flatten=_flatten,
        sort_key=lambda m: ((m.get("code") or "").lower(), m.get("notetype_id") or ""),
    )
