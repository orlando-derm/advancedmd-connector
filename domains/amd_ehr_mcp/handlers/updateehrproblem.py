"""amd_ehr_updateehrproblem — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "updateehrproblem"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("updateehrproblem",)

async def handle(*, problem_id: Any, updates: Any) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
