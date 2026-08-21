"""amd_masterfiles_select_diagnosis_codes — count only, no raw.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
Adam should query specific codes via lookup_icd10, not enumerate the
master file.
"""
from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "selectdiagnosiscodes"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("selectdiagnosiscodes",)


async def handle(*, include_inactive: Any = False) -> dict[str, Any]:
    client = get_client()
    call_kwargs = {"include_inactive": include_inactive}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="selectdiagnosiscodes", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {**err}
    rows = extract_rows_by_tag(raw_dict, "diagcode")
    if not rows:
        rows = extract_rows_by_tag(raw_dict, "diagnosis")
    return {
        "count": len(rows),
    }
