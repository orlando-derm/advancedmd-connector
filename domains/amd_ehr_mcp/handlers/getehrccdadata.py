"""amd_ehr_get_ehr_ccda_data — BETA EHR. Boolean found only, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
CCDA is a single-document export; surface only a boolean.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import get_client, raw_to_dict

ACTION = "getehrccdadata"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getehrccdadata",)

async def handle(*, patient_id: str) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"patient_id": patient_id}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="getehrccdadata", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"patient_id": patient_id, **err}
    return {
        "patient_id": patient_id,
        "found": bool(raw_dict),
    }
