from __future__ import annotations
from typing import Any
from amd_mcp_common.errors import safe_amd_call
from ._common import get_client, raw_to_dict

ACTION = "getcustomdata"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getcustomdata",)


async def handle(*, patient_id: str, includeindemographics: Any = 0) -> dict[str, Any]:
    client = get_client()
    # AMD's getcustomdata expects `patientid=` on the wire, not `patient_id`.
    # Adam-facing schema keeps the snake_case ergonomic name; wire-level
    # rename happens here. Confirmed against docx attribute list for
    # the "Get Custom Patient Data" section. Promoted into scope by the
    # 2026-06-04 auditor pair (RISK-A AUDIT-3).
    call_kwargs = {"patientid": patient_id, "includeindemographics": includeindemographics}
    call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None and v != ""}
    raw_dict, err = safe_amd_call(client, action="getcustomdata", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"patient_id": patient_id, **err}
    # Aaron 2026-06-04: NO raw AMD blob. Single-row endpoint — surface
    # only the patient_id echo + the boolean "found" cardinality.
    # If a downstream feature needs custom-field detail, build a typed
    # projector in the handler (not the LLM).
    return {
        "patient_id": patient_id,
        "found": bool(raw_dict),
    }
