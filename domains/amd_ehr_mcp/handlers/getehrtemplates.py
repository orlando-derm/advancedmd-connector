"""amd_ehr_get_ehr_templates — BETA EHR. Count only, no raw."""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import count_rows_for_tags, get_client, raw_to_dict

ACTION = "getehrtemplates"
WRITE_ACTION = False
TIER = 1
PERMITTED_ACTIONS = ("getehrtemplates",)

async def handle() -> dict[str, Any]:
    client = get_client()
    raw_dict, err = safe_amd_call(client, action="getehrtemplates", raw_to_dict_fn=raw_to_dict)
    if err is not None:
        return {**err}
    return {
        "count": count_rows_for_tags(raw_dict, "template", "ehrtemplate"),
    }
