"""amd_payments_add_payments - WRITE STUB.

Exists ONLY to prove that WRITE_TOOLS_ENABLED=False filters write
handlers from list_tools() and the call_tool dispatch table. Calling
this handler when WRITE_TOOLS_ENABLED=True would attempt an AMD write,
but the foundation plan keeps the flag False.

Doc source (intended): runtime/cache/amd-doc-extract.md:5881
(paraphrased per NDA). class="paymententry" per action-catalog
(not "api"). Posts a payment for a patient (applied against
chargelist OR placed on unappliedpaymentlist).
"""
from __future__ import annotations

from typing import Any


ACTION = "addpayments"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("addpayments",)


async def handle(
    *,
    patient_id: str,
    amount: str,
    paycode: str,
    paysource: int | None = None,
    paymethod: int | None = None,
    checknumber: str = "",
    carrierid: str = "",
    profile_id: str = "",
    checkout: int = 0,
    date: str = "",
    batch: str = "",
) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; this stub exists to prove the "
        "WRITE_TOOLS_ENABLED=False filter excludes it from list_tools()."
    )
