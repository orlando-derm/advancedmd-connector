"""amd_ehr_get_ehr_updated_notes — BETA EHR. Count only, no raw."""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import count_rows_for_tags, get_client, raw_to_dict

ACTION = "getehrupdatednotes"
WRITE_ACTION = False
TIER = 1
PERMITTED_ACTIONS = ("getehrupdatednotes",)

async def handle(*, since: str) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"since": since}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="getehrupdatednotes", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"since": since, **err}
    return {
        "since": since,
        "count": count_rows_for_tags(raw_dict, "note", "ehrnote"),
    }
