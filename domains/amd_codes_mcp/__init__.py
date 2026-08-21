"""amd_codes_mcp: per-domain MCP server for AMD's codes API surface.

CPT, ICD-10, HCPCS, modifier code lookups. Pure read-only reference
data — no write actions exist for this domain.

Sibling to amd_patients_mcp and amd_visits_mcp. Scaffolded in C3.2 of
`amd-mcp-server-common/READONLY_COMPLETION_PLAN.txt`; handlers wired
in C3.3, policies in C3.4.
"""
from __future__ import annotations
