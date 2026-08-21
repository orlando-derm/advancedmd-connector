"""amd_visits_add_visit - WRITE STUB.

Exists ONLY to prove that WRITE_TOOLS_ENABLED=False filters write
handlers from list_tools() and the call_tool dispatch table. Calling
this handler when WRITE_TOOLS_ENABLED=True would attempt an AMD write,
but the foundation plan keeps the flag False.

Doc source (intended): knowledge/reference/amd_api/visits/addvisit.md
Class is "chargeentry" per action-catalog (not "api").
"""
from __future__ import annotations

from typing import Any


ACTION = "addvisit"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("addvisit",)


async def handle(
    *,
    patient_id: str,
    profile_id: str,
    date: str = "",
    refplan_id: str | None = None,
) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; this stub exists to prove the "
        "WRITE_TOOLS_ENABLED=False filter excludes it from list_tools()."
    )
