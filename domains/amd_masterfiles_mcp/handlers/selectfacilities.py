"""amd_masterfiles_select_facilities — count only, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
Master-file enumeration is not Adam's job; Adam only learns "there are
N facilities" — concrete ids/names come from a typed UI or a downstream
handler that's not enumerating.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "selectfacilities"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("selectfacilities",)


async def handle(*, active_only: Any = False) -> dict[str, Any]:
    client = get_client()
    # AMD's selectfacilities expects `type=0/1` on the wire (0=all,
    # 1=active-only), not a boolean `active_only`. Adam-facing schema
    # keeps the readable `active_only: bool`; wire-level translation
    # happens here. Per docx "Master File Requests / Selecting Facility
    # File Templates". Promoted into scope by the 2026-06-04 auditor
    # pair (AUDIT-3).
    wire_type = "1" if bool(active_only) else "0"
    call_kwargs = {"type": wire_type}
    raw_dict, err = safe_amd_call(client, action="selectfacilities", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"active_only": bool(active_only), **err}
    rows = extract_rows_by_tag(raw_dict, "facility")
    return {
        "active_only": bool(active_only),
        "count": len(rows),
    }
