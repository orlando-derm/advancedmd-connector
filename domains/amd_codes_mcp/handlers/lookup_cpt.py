"""amd_codes_lookup_cpt — AMD lookup action with class=cpt (proccode).

Wraps AMD's lookupproccode-class endpoint. Codes are NOT PHI.

Returns `{query, count, matches (cap 5), narrow_query}` where each
match is `{code, name, id}`. Sort: code asc. Aaron 2026-06-04: no raw
AMD blob, matches capped so Adam never enumerates or counts.
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import enriched_codes_response, get_client, raw_to_dict


ACTION = "lookup-cpt"  # catalog name
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupproccode",)


async def handle(*, query: str) -> dict[str, Any]:
    if not query:
        return {"error": "bad_input", "details": {"reason": "query required"}}
    client = get_client()
    # Live verification 2026-06-04: action="lookupproccode", class_="api",
    # code=<query> returns the matching CPT row (verified with 99213).
    # The legacy generic `action="lookup", class_="cpt", search=` shape
    # fails on this office key with "PPMD_cpt.cpt instance" error — the
    # same pattern that broke patient lookup (DRIFT-4). Auditor pair
    # RISK-C, smoke-confirmed.
    raw_dict, err = safe_amd_call(
        client, action="lookupproccode", raw_to_dict_fn=raw_to_dict,
        class_="api", code=query,
    )
    if err is not None:
        return {"query": query, **err}
    return enriched_codes_response(raw_dict, row_tag="proccode", query=query)
