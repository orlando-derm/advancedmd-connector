"""amd_system_get_sys_defaults — single-row, found-flag only.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import get_client, raw_to_dict

ACTION = "getsysdefaults"
WRITE_ACTION = False
TIER = 1
PERMITTED_ACTIONS = ("getsysdefaults",)

async def handle(*, category_filter: Any = None) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"category_filter": category_filter}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="getsysdefaults", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {**err}
    return {
        "found": bool(raw_dict),
    }
