"""amd_ehr_addehrhwplans — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "addehrhwplans"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("addehrhwplans",)

async def handle(*, patient_id: Any, plan: Any) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
