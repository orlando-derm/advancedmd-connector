"""amd_ehr_get_ehr_hw_plans — BETA EHR. Count only, no raw."""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import count_rows_for_tags, get_client, raw_to_dict

ACTION = "getehrhwplans"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getehrhwplans",)

async def handle(*, patient_id: str) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"patient_id": patient_id}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="getehrhwplans", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"patient_id": patient_id, **err}
    return {
        "patient_id": patient_id,
        "count": count_rows_for_tags(raw_dict, "hwplan", "plan", "healthplan"),
    }
