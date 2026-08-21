"""Audit log v2 (JSONL).

Emits one JSON-Lines record per tool call. Schema documented in
``docs/audit-log-v2.md`` and validated by ``audit-v2.schema.json``.

Atomic-append writes; per-server log file means no concurrent-process
contention. Within a process, concurrent thread writes produce
line-atomic JSON.

Default path: ``runtime/audits/<server_name>/v2-audit.log``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "amd-mcp-audit/v2"


def _workspace_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "knowledge").is_dir() and (parent / "runtime").is_dir():
            return parent
    return Path.cwd()


def _default_log_path(server_name: str) -> Path:
    return _workspace_root() / "runtime" / "audits" / server_name / "v2-audit.log"


def emit_v2(
    *,
    call_id: str,
    tool_name: str,
    action: str,
    domain: str,
    server_name: str,
    args_redacted: dict[str, Any],
    phi_fields_revealed: Iterable[str],
    office_key: str,
    tier: int,
    outcome: str,
    duration_ms: int | None,
    rate_limit_peak: bool | None,
    ts: datetime | None = None,
    path: Path | None = None,
) -> Path:
    """Append one JSON-Lines record. Returns the log path."""
    if ts is None:
        ts = datetime.now(timezone.utc)
    target = path if path is not None else _default_log_path(server_name)
    override = os.environ.get("AMD_MCP_AUDIT_LOG_DIR")
    if path is None and override:
        target = Path(override) / server_name / "v2-audit.log"
    target.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "schema_version": SCHEMA_VERSION,
        "ts": ts.isoformat(),
        "call_id": call_id,
        "domain": domain,
        "server_name": server_name,
        "tool": tool_name,
        "action": action,
        "office_key": office_key,
        "tier": tier,
        "args_redacted": args_redacted,
        "phi_fields_revealed": sorted(phi_fields_revealed),
        "outcome": outcome,
        "duration_ms": duration_ms,
        "rate_limit_peak": rate_limit_peak,
    }
    # Atomic-line append: O_APPEND + single-write semantics.
    line = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line)
    return target


def read_all(path: Path) -> list[dict[str, Any]]:
    """Test helper: read every record from the log file."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# Convenience: a callable matching base_server.wrap_tool's audit_emit signature.
def make_emitter(server_name: str):
    def _emit(**kwargs):
        kwargs.setdefault("server_name", server_name)
        return emit_v2(**kwargs)
    return _emit
