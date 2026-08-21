"""Build ToolSpec list from handler modules + loaded policies.

At boot, server.py calls ``build_specs(policies, schemas, client)``.
The factory:

  1. Iterates the handler modules in `_HANDLER_MODULES`.
  2. For each, reads ACTION / WRITE_ACTION / TIER / PERMITTED_ACTIONS.
  3. Matches against the loaded policy (keyed by ACTION).
  4. Builds an mcp.types.Tool with name from policy.tool_name +
     inputSchema from the loaded JSON Schema.
  5. Returns a list of ToolSpec.

C5.3: `_HANDLER_MODULES` populated with the two payments actions
(1 read + 1 write stub). The write stub is filtered from list_tools()
by base_server.register_all() when WRITE_TOOLS_ENABLED=False.
"""
from __future__ import annotations

from typing import Any

import mcp.types as mcp_types

from amd_mcp_common.base_server import ToolSpec
from amd_mcp_common.knowledge_loader import ActionPolicy

from . import (
    addpayments,
    gettxhistory,
)


# Each (module, action_key_used_to_match_policy).
_HANDLER_MODULES: tuple = (
    gettxhistory,
    addpayments,
)


def build_specs(
    *,
    policies: dict[str, ActionPolicy],
    schemas: dict[str, dict[str, Any]],
) -> list[ToolSpec]:
    """Assemble ToolSpec list from handler modules + policies + schemas.

    Skips any handler whose policy is missing (logs a warning).
    """
    specs: list[ToolSpec] = []
    for mod in _HANDLER_MODULES:
        action_key = mod.ACTION
        policy = policies.get(action_key)
        if policy is None:
            # No policy means no MCP tool exposure. Aaron-curated layer.
            import logging
            logging.getLogger("amd_payments_mcp.factory").warning(
                "handler %r has ACTION=%r but no matching policy file; "
                "skipping.",
                mod.__name__, action_key,
            )
            continue
        schema = schemas.get(action_key, {"type": "object"})
        # Strip top-level metadata from the input schema (the LLM-facing
        # tool schema is the raw structural shape).
        input_schema = {k: v for k, v in schema.items()
                        if not k.startswith("x-") and k not in ("$schema", "$id")}
        # `description` lives in the Tool, not the inputSchema.
        description = input_schema.pop("description", None) or policy.action

        tool = mcp_types.Tool(
            name=policy.tool_name,
            description=description,
            inputSchema=input_schema,
        )
        specs.append(ToolSpec(
            tool=tool,
            handler=mod.handle,
            tier=policy.tier,
            permitted_actions=tuple(policy.permitted_actions),
            action=action_key,
            domain=policy.domain,
            write_action=getattr(mod, "WRITE_ACTION", False) or policy.write_action,
            policy=policy,
            schema_id=schema.get("$id"),
            policy_id=f"amd-mcp-policy/v1#{action_key}",
        ))
    return specs
