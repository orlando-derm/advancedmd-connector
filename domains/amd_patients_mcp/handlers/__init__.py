"""Per-action handlers for amd-patients-mcp.

Each handler module exports:
  ACTION              raw AMD action string
  WRITE_ACTION        bool — True for write-tool stubs
  TIER                AMD rate-limit tier (1/2/3)
  PERMITTED_ACTIONS   tuple for AMDActionGuard allowlist
  handle              async callable

The factory in _factory.py assembles `ToolSpec`s from the loaded
policies + the per-handler module attributes.
"""
from __future__ import annotations
