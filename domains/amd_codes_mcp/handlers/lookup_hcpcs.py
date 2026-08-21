"""amd_codes_lookup_hcpcs — AMD lookup action with class=hcpcs.

Returns `{query, count, matches (cap 5), narrow_query}` where each
match is `{code, name, id}`. Sort: code asc.
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import enriched_codes_response, get_client, raw_to_dict


ACTION = "lookup-hcpcs"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupproccode",)


async def handle(*, query: str) -> dict[str, Any]:
    if not query:
        return {"error": "bad_input", "details": {"reason": "query required"}}
    client = get_client()
    # Live verification 2026-06-04: HCPCS codes (e.g. "J3301") flow through
    # the SAME endpoint as CPT — action="lookupproccode", class_="api",
    # code=<query>. There is no separate `lookuphcpcs` action (AMD
    # returns "Action lookuphcpcs not found"). The generic shape with
    # class_="hcpcs" fails with "PPMD_hcpcs.hcpcs" instance error.
    # Auditor pair RISK-C, smoke-confirmed.
    raw_dict, err = safe_amd_call(
        client, action="lookupproccode", raw_to_dict_fn=raw_to_dict,
        class_="api", code=query,
    )
    if err is not None:
        return {"query": query, **err}
    return enriched_codes_response(raw_dict, row_tag="hcpcs", query=query)
