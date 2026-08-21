"""amd_patients_updateinsurance — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "updateinsurance"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("updateinsurance",)

async def handle(*, patient_id: Any, insplan_id: Any, sequence: Any = None, updates: Any) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
