"""amd_patients_get_demographic — AMD getdemographic action.

Doc source: knowledge/reference/amd_api/patients/getdemographic.md
"""
from __future__ import annotations

from typing import Any

from ._common import get_client, serialize


ACTION = "getdemographic"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getdemographic",)


async def handle(
    *,
    patient_id: str | None = None,
    chart_number: str | None = None,
    class_: str = "demographics",
) -> dict[str, Any]:
    if not patient_id and not chart_number:
        return {
            "error": "bad_input",
            "details": {"reason": "patient_id or chart_number required"},
        }
    client = get_client()
    if patient_id:
        bundle = client.get_patient_bundle(patient_id=patient_id)
    else:
        bundle = client.get_patient_bundle(chart_number=chart_number)
    return {"patient": serialize(bundle)}
