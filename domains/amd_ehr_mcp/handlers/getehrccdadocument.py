"""amd_ehr_get_ehr_ccda_document — BETA EHR (DUO-5). Boolean only.

DUO-5 RULING: handler-level body replacement of the ClinicalDocument
XML string is MANDATORY. amd_mcp_common.redact._walk returns string
values unchanged (verified lines 266-278), so policy
phi_fields:["ClinicalDocument"] is supplementary defense only.

Aaron 2026-06-04: "it cannot do any math or aggregations properly."
The CCDA document body is multi-MB clinical narrative; Adam absolutely
never reads it. We surface only a boolean.
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import get_client, raw_to_dict


ACTION = "getehrccdadocument"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getehrccdadocument",)


async def handle(*, patient_id: str) -> dict[str, Any]:
    client = get_client()
    raw_dict, err = safe_amd_call(client, action="getehrccdadocument", raw_to_dict_fn=raw_to_dict, patient_id=patient_id)
    if err is not None:
        return {"patient_id": patient_id, **err}
    return {
        "patient_id": patient_id,
        "found": bool(raw_dict),
    }
