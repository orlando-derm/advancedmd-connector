"""amd_masterfiles_lookup_carrier — capped matches, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import capped_match_response, get_client, raw_to_dict

ACTION = "lookupcarrier"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupcarrier",)


def _flatten(row: dict) -> dict[str, str]:
    return {
        "carrier_id": row.get("id", ""),
        "name": row.get("name", ""),
        "code": row.get("code", ""),
    }


async def handle(*, query: str, subtype: Any = None) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupcarrier (named action, class_="lookup") takes `name=`
    # on the wire (docx sample line 5834:
    # <ppmdmsg action="lookupcarrier" class="lookup" ... name="c"
    #          orderby="name" page="1"><subtype filter-activeonly="true"/>
    # </ppmdmsg>).
    # Sibling: the legacy generic `action="lookup", class_="carrier"`
    # uses `search=` (see amd-mcp-server/tools/lookups.py:91).
    # [AARON-REVIEWABLE-DRIFT-1] subtype: docx 5834 shows subtype as a
    # CHILD element. Leaving the attr-style pass-through until a
    # child-element helper exists.
    call_kwargs: dict[str, Any] = {"name": query}
    if subtype not in (None, ""):
        call_kwargs["subtype"] = subtype
    raw_dict, err = safe_amd_call(client, action="lookupcarrier", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    return capped_match_response(
        raw_dict, row_tag="carrier", query=query, flatten=_flatten,
        sort_key=lambda m: ((m.get("name") or "").lower(), m.get("carrier_id") or ""),
    )
