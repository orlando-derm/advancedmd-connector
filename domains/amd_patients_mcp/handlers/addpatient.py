"""amd_patients_addpatient — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "addpatient"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("addpatient",)

async def handle(*, first_name: Any, last_name: Any, dob: Any, sex: Any = None, ssn: Any = None, profile: Any, respparty_name: Any = None, address: Any = None, contactinfo: Any = None) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
