from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import enriched_codes_response, get_client, raw_to_dict

ACTION = "lookupproccode"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupproccode",)

async def handle(*, query: str, subtype: Any = None) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupproccode action uses `code=` as the search criterion
    # (docx Section "Lookup Requests" sample line:
    # <ppmdmsg action="lookupproccode" ... code="99212" page="1" />).
    # The Adam-facing handler arg stays `query` for ergonomic parity
    # with the lookup-cpt family; the wire rename happens here.
    # [AARON-REVIEWABLE-DRIFT-1] subtype: docx 5829 specifies subtype as
    # a CHILD element <subtype name="..."/>, not an attribute. Leaving
    # the existing attr-style pass-through until a child-element helper
    # exists; AMD may accept either.
    call_kwargs: dict[str, Any] = {"code": query}
    if subtype not in (None, ""):
        call_kwargs["subtype"] = subtype
    raw_dict, err = safe_amd_call(client, action="lookupproccode", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    # Aaron 2026-06-04: no raw AMD blob; matches cap to 5 + narrow_query
    # flag so Adam never enumerates or counts. Mirror lookup_cpt.py.
    return enriched_codes_response(raw_dict, row_tag="proccode", query=query)
