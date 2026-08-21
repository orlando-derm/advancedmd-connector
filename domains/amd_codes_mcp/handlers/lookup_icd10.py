"""amd_codes_lookup_icd10 — AMD lookup action with class=diagcode (ICD-10).

Wraps AMD's lookupdiagcode-class endpoint with codeset="10" implicit.

Returns `{query, count, matches (cap 5), narrow_query}` where each
match is `{code, name, id}`. Sort: code asc.
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import enriched_codes_response, get_client, raw_to_dict


ACTION = "lookup-icd10"  # catalog name
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupdiagcode",)


async def handle(*, query: str) -> dict[str, Any]:
    if not query:
        return {"error": "bad_input", "details": {"reason": "query required"}}
    client = get_client()
    # Live verification 2026-06-04: action="lookupdiagcode", class_="api",
    # code=<query>, codeset="10" returns matching ICD-10 rows (verified
    # with "L82.1" → 1 row). Note: AMD requires the FULL code with the
    # subcategory ("L82.1") — passing just "L82" returns 0 rows. Adam-
    # facing schema lets callers pass any string; that's a user-side
    # limitation, not a bug. The legacy generic "lookup, class_=diagcode"
    # shape fails on this office key with "PPMD_diagcode.diagcode"
    # instance error (auditor pair RISK-C, smoke-confirmed).
    raw_dict, err = safe_amd_call(
        client, action="lookupdiagcode", raw_to_dict_fn=raw_to_dict,
        class_="api", code=query, codeset="10",
    )
    if err is not None:
        return {"query": query, **err}
    return enriched_codes_response(raw_dict, row_tag="diagcode", query=query)
