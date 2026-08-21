"""amd_masterfiles_select_user_file_templates — count only, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
Master-file enumeration is not Adam's job.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "selectuserfiletemplates"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("selectuserfiletemplates",)


async def handle(*, template_type: Any = None) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"template_type": template_type}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="selectuserfiletemplates", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {**err}
    rows = extract_rows_by_tag(raw_dict, "template")
    if not rows:
        rows = extract_rows_by_tag(raw_dict, "userfile")
    return {
        "count": len(rows),
    }
