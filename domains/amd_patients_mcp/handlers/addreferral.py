"""amd_patients_addreferral — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "addreferral"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("addreferral",)

async def handle(*, patient_id: Any, refprov_id: Any, reason: Any = None, proccode: Any = None, begin_date: Any = None, end_date: Any = None, max_visits: Any = None, max_amount: Any = None) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
