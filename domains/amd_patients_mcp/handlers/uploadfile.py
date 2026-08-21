"""amd_patients_uploadfile — WRITE STUB.

Exists ONLY to prove WRITE_TOOLS_ENABLED=False filters writes from
list_tools(). Calling when the flag is True would attempt an AMD write.
"""
from __future__ import annotations
from typing import Any

ACTION = "uploadfile"
WRITE_ACTION = True
TIER = 2
PERMITTED_ACTIONS = ("uploadfile",)

async def handle(*, patient_id: Any, file_name: Any, file_ext: Any = None, filetype: Any = None, description: Any = None, file_contents_b64: Any, local_file_size_hint_kb: Any = None) -> dict[str, Any]:
    # DUO-13: handler-level 1024kb hard cap (complements policy.requires_streaming).
    if local_file_size_hint_kb is not None and int(local_file_size_hint_kb) > 1024:
        return {"error": "too_large", "details": {"limit_kb": 1024, "hint_kb": int(local_file_size_hint_kb)}}
    # Best-effort base64 length check when hint is absent.
    if file_contents_b64 and len(file_contents_b64) > 1024 * 1024 * 4 // 3:
        return {"error": "too_large", "details": {"limit_kb": 1024}}
    raise NotImplementedError(
        "Write tools disabled; WRITE_TOOLS_ENABLED=False filter excludes this stub from list_tools()."
    )
