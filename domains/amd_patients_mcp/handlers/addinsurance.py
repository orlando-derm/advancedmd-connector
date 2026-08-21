"""amd_patients_addinsurance — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "addinsurance"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("addinsurance",)

async def handle(*, patient_id: Any, carrier_id: Any, subscriber_id: Any = None, subscriber_num: Any, begin_date: Any = None, relationship: Any = None, coverage: Any = None) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
