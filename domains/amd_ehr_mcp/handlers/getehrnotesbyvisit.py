"""amd_ehr_get_ehr_notes_by_visit — BETA EHR. Count only, no raw."""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import count_rows_for_tags, get_client, raw_to_dict

ACTION = "getehrnotesbyvisit"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getehrnotesbyvisit",)

async def handle(*, visit_id: str) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"visit_id": visit_id}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="getehrnotesbyvisit", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"visit_id": visit_id, **err}
    return {
        "visit_id": visit_id,
        "count": count_rows_for_tags(raw_dict, "note", "ehrnote"),
    }
