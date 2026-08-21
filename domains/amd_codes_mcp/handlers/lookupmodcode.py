from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import enriched_codes_response, get_client, raw_to_dict

ACTION = "lookupmodcode"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupmodcode",)

async def handle(*, query: str, subtype: Any = None) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupmodcode action uses `code=` as the search criterion
    # (docx sample line 5858:
    # <ppmdmsg action="lookupmodcode" ... code="" page="1" />).
    # [AARON-REVIEWABLE-DRIFT-1] subtype: see lookupproccode.py note.
    call_kwargs: dict[str, Any] = {"code": query}
    if subtype not in (None, ""):
        call_kwargs["subtype"] = subtype
    raw_dict, err = safe_amd_call(client, action="lookupmodcode", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    # Aaron 2026-06-04: no raw AMD blob; matches cap to 5 + narrow_query.
    return enriched_codes_response(raw_dict, row_tag="modcode", query=query)
