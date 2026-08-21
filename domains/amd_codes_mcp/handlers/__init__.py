"""Per-action handlers for amd-codes-mcp.

Each handler module exports:
  ACTION              catalog action name (e.g. "lookup-cpt")
  WRITE_ACTION        bool - always False for codes (pure read-only)
  TIER                AMD rate-limit tier (always 3 for codes)
  PERMITTED_ACTIONS   tuple for AMDActionGuard allowlist
                      (always ("lookup", {"class_": {"<class>"}}) form)
  handle              async callable

The factory in _factory.py assembles `ToolSpec`s from the loaded
policies + the per-handler module attributes.
"""
from __future__ import annotations
