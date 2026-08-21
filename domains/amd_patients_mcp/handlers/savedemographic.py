"""amd_patients_save_demographic — WRITE STUB.

Exists ONLY to prove that WRITE_TOOLS_ENABLED=False filters write
handlers from list_tools() and the call_tool dispatch table. Calling
this handler when WRITE_TOOLS_ENABLED=True would attempt an AMD write,
but the foundation plan keeps the flag False.
"""
from __future__ import annotations

from typing import Any


ACTION = "savedemographic"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("savedemographic",)


async def handle(*, patient_id: str, updates: dict) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; this stub exists to prove the "
        "WRITE_TOOLS_ENABLED=False filter excludes it from list_tools()."
    )
