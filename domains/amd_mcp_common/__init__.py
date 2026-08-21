"""amd_mcp_common: shared library for per-domain AMD MCP servers.

Foundation-phase scaffolding. Public exports land in subsequent F-phases:
- F2 lands schema_gen + schema_loader.
- F3 lands redact / action_guard / errors / rate_limit / config /
  base_server / knowledge_loader.
- F4 lands audit + audit_v1_adapter.

See `amd-mcp-server-common/memory/decisions/INDEX.md` for the locked
architectural decisions that gate the design.
"""
from __future__ import annotations
