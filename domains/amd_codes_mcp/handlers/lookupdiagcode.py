from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import enriched_codes_response, get_client, raw_to_dict

ACTION = "lookupdiagcode"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupdiagcode",)

async def handle(*, query: str, subtype: Any = None) -> dict[str, Any]:
    client = get_client()
    # AMD's lookupdiagcode action uses `code=` as the search criterion
    # (docx sample line 5855:
    # <ppmdmsg action="lookupdiagcode" ... code="300.01" page="1" />).
    # codeset="10" auto-imports ICD-10 codes per docx 5832.
    # [AARON-REVIEWABLE-DRIFT-1] subtype: see lookupproccode.py note.
    call_kwargs: dict[str, Any] = {"code": query, "codeset": "10"}
    if subtype not in (None, ""):
        call_kwargs["subtype"] = subtype
    raw_dict, err = safe_amd_call(client, action="lookupdiagcode", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"query": query, **err}
    # Aaron 2026-06-04: no raw AMD blob; matches cap to 5 + narrow_query
    # flag. Mirror lookup_icd10.py.
    return enriched_codes_response(raw_dict, row_tag="diagcode", query=query)
