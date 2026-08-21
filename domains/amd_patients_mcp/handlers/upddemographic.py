"""amd_patients_upd_demographic — WRITE STUB.

See savedemographic.py — same rationale.
"""
from __future__ import annotations

from typing import Any


ACTION = "upddemographic"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("upddemographic",)


async def handle(*, patient_id: str, updates: dict) -> dict[str, Any]:
    raise NotImplementedError(
        "Write tools disabled; this stub exists to prove the "
        "WRITE_TOOLS_ENABLED=False filter excludes it from list_tools()."
    )
