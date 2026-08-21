"""Translate legacy v1 audit records into v2 shape for cross-domain replay.

Legacy v1 schema (from `amd-mcp-server/src/amd_mcp/audit.py`):

  {
    "ts": "...", "call_id": "...", "tool": "...",
    "office_key": "...", "args_redacted": {...},
    "phi_fields_revealed": [...]
  }

v2 adds: schema_version, domain, server_name, action, outcome, tier,
duration_ms, rate_limit_peak. Missing values are filled with
documented sentinels (see docs/audit-log-v2.md).
"""
from __future__ import annotations

from typing import Any


def translate(v1: dict[str, Any]) -> dict[str, Any]:
    """v1 record -> v2 record (dict). Lossless for present fields."""
    return {
        "schema_version": "amd-mcp-audit/v2",
        "ts": v1.get("ts", ""),
        "call_id": v1.get("call_id", ""),
        "domain": "legacy",
        "server_name": "amd-mcp-server",
        "tool": v1.get("tool", ""),
        "action": "unknown",        # v1 didn't carry it
        "office_key": v1.get("office_key", ""),
        "tier": 2,                   # most common v1 tier
        "args_redacted": v1.get("args_redacted", {}),
        "phi_fields_revealed": v1.get("phi_fields_revealed", []),
        "outcome": "ok",             # v1 only logged successful PHI-revealing calls
        "duration_ms": None,
        "rate_limit_peak": None,
    }
