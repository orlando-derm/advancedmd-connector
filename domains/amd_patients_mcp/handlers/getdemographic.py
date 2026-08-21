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
    """Fetch one patient's demographic bundle.

    SPEC Appendix C defect 2, fixed here: this handler used to forward
    chart_number into client.get_patient_bundle(), which builds a
    patientid-only request. That silently sent a chart number as a
    patient id. The chart-number path has no confirmed AMD attribute in
    any reference client, and inventing one would spend an AMD call to
    learn nothing, so it is refused up front instead. Recorded as an open
    item in docs/TOOL_TO_XML_MAP.md.
    """
    if not patient_id and not chart_number:
        return {
            "error": "bad_input",
            "details": {"reason": "patient_id or chart_number required"},
        }
    if not patient_id:
        return {
            "error": "bad_input",
            "details": {
                "reason": (
                    "chart_number lookup is not verified for getdemographic; "
                    "resolve the chart number to a patient_id first "
                    "(amd_patients_lookup_patient) and call again"
                )
            },
        }
    client = get_client()
    bundle = await client.get_patient_bundle(patient_id=patient_id)
    return {"patient": serialize(bundle)}
