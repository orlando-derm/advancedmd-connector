"""amd_billing_save_charges - WRITE STUB.

Exists ONLY to prove that WRITE_TOOLS_ENABLED=False filters write
handlers from list_tools() and the call_tool dispatch table. Calling
this handler when WRITE_TOOLS_ENABLED=True would attempt an AMD write,
but the foundation plan keeps the flag False.

Doc source (intended): raw AMD doc extract line 5512
(`<ppmdmsg action="savecharges" class="api" ...>`). Class is "api".
Per AMD doc: "This method will void any charges that exist on the
visit and will post the charges in the chargelist element of the call."
"""
from __future__ import annotations

from typing import Any


ACTION = "savecharges"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("savecharges",)


async def handle(
    *,
    patient_id: str,
    visit_id: str,
    chargelist: list,
    force: int = 0,
) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; this stub exists to prove the "
        "WRITE_TOOLS_ENABLED=False filter excludes it from list_tools()."
    )
