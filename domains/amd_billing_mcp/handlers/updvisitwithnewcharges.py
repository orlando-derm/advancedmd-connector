"""amd_billing_upd_visit_with_new_charges - WRITE STUB.

Exists ONLY to prove that WRITE_TOOLS_ENABLED=False filters write
handlers from list_tools() and the call_tool dispatch table. Calling
this handler when WRITE_TOOLS_ENABLED=True would attempt an AMD write,
but the foundation plan keeps the flag False.

Doc source (intended): raw AMD doc extract line 5419/5423
(`<ppmdmsg action="updvisitwithnewcharges" class="chargeentry"
 msgtime="..." patientid="..." episodeid="..." approval="0|1">`).
Class is "chargeentry" (not "api").
"""
from __future__ import annotations

from typing import Any


ACTION = "updvisitwithnewcharges"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("updvisitwithnewcharges",)


async def handle(
    *,
    patient_id: str,
    episode_id: str,
    chargelist: list,
    approval: int = 0,
) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; this stub exists to prove the "
        "WRITE_TOOLS_ENABLED=False filter excludes it from list_tools()."
    )
