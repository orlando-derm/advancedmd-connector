"""Build ToolSpec list from handler modules + loaded policies."""
from __future__ import annotations

from typing import Any

import mcp.types as mcp_types

from amd_mcp_common.base_server import ToolSpec
from amd_mcp_common.knowledge_loader import ActionPolicy

from . import (
    getsysdefaults,
)


_HANDLER_MODULES: tuple = (
    getsysdefaults,
)


def build_specs(
    *,
    policies: dict[str, ActionPolicy],
    schemas: dict[str, dict[str, Any]],
) -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for mod in _HANDLER_MODULES:
        action_key = mod.ACTION
        policy = policies.get(action_key)
        if policy is None:
            import logging
            logging.getLogger("amd_system_mcp.factory").warning(
                "handler %r has ACTION=%r but no matching policy file; skipping.",
                mod.__name__, action_key,
            )
            continue
        # DUO-1 / AUDIT-2 FC-4: filter meta-domain or null tool_name policies.
        if policy.domain == "meta" or policy.tool_name is None:
            continue
        schema = schemas.get(action_key, {"type": "object"})
        input_schema = {k: v for k, v in schema.items()
                        if not k.startswith("x-") and k not in ("$schema", "$id")}
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
            policy_id=f"amd-mcp-policy/v1.1#{action_key}",
        ))
    return specs
