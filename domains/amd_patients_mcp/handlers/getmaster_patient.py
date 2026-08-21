"""amd_patients_get_master — AMD getmaster action with class=patient."""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import get_client, raw_to_dict


ACTION = "getmaster-patient"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = (("getmaster", {"class_": {"patient"}}),)


async def handle(*, patient_id: str) -> dict[str, Any]:
    if not patient_id:
        return {"error": "bad_input", "details": {"reason": "patient_id required"}}
    client = get_client()
    raw_dict, err = safe_amd_call(
        client, action="getmaster", raw_to_dict_fn=raw_to_dict,
        class_="patient", patient_id=patient_id,
    )
    if err is not None:
        return {"patient_id": patient_id, **err}
    # Aaron 2026-06-04: NO raw AMD blob. Single-row endpoint — surface
    # only the patient_id echo + a "found" flag. If a downstream feature
    # needs demographic detail, route through getdemographic (which is
    # already field-projected + redacted) instead of this raw master
    # file dump.
    return {
        "patient_id": patient_id,
        "found": bool(raw_dict),
    }
