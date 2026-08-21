"""amd_patients_savepatientnotes — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "savepatientnotes"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("savepatientnotes",)

async def handle(*, patient_id: Any, note_type: Any = None, note_text: Any) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
