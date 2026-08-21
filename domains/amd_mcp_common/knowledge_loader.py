"""Per-action policy loader.

Reads every ``<action>.policy.data.json`` under
``knowledge_root/integrations/amd/<domain>/`` and returns a dict
keyed by raw AMD action.

Validates each file against ``amd-mcp-server-common/policy.schema.json``;
invalid files raise with the filename for fast triage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError as _JsonValidationError


@dataclass
class ActionPolicy:
    """Per-action policy dataclass, mirror of policy.data.json shape."""

    action: str
    domain: str
    tier: int
    # tool_name may be None for catalog-only meta-domain entries (DUO-1,
    # AUDIT-2 FC-4). Non-meta policies must keep tool_name a non-empty string;
    # the JSON Schema's if/then on domain == 'meta' enforces this.
    tool_name: str | None
    permitted_actions: tuple[Any, ...]
    write_action: bool = False
    redact: dict[str, Any] = field(default_factory=dict)
    permission: dict[str, Any] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionPolicy":
        # Normalize permitted_actions: list of (str | [str, dict]) -> tuple.
        raw_pa = data.get("permitted_actions", [])
        normalized_pa: list[Any] = []
        for entry in raw_pa:
            if isinstance(entry, list) and len(entry) == 2:
                action, filt = entry
                normalized_pa.append((action, filt))
            else:
                normalized_pa.append(entry)
        return cls(
            action=data["action"],
            domain=data["domain"],
            tier=data["tier"],
            tool_name=data["tool_name"],
            permitted_actions=tuple(normalized_pa),
            write_action=bool(data.get("write_action", False)),
            redact=dict(data.get("redact") or {}),
            permission=dict(data.get("permission") or {}),
            audit=dict(data.get("audit") or {}),
            raw=dict(data),
        )


def _policy_schema_path() -> Path:
    here = Path(__file__).resolve()
    return here.parent.parent.parent / "policy.schema.json"


_validator: Draft202012Validator | None = None


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        schema_path = _policy_schema_path()
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        _validator = Draft202012Validator(schema)
    return _validator


def load_policies(domain: str, knowledge_root: Path) -> dict[str, ActionPolicy]:
    """Load all policies for a domain.

    Returns ``{action_string: ActionPolicy}``.

    - Empty dict if the domain subdir doesn't exist (per F0.D5).
    - Raises ``ValueError`` with the filename for any invalid file.
    """
    domain_dir = knowledge_root / "integrations" / "amd" / domain
    if not domain_dir.is_dir():
        return {}
    out: dict[str, ActionPolicy] = {}
    validator = _get_validator()
    for path in sorted(domain_dir.glob("*.policy.data.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON: {exc}") from exc
        errors = list(validator.iter_errors(data))
        if errors:
            err = errors[0]
            raise ValueError(
                f"{path}: policy schema violation at "
                f"{'/'.join(str(p) for p in err.path)!r}: {err.message}"
            )
        if "action" not in data:
            raise ValueError(f"{path}: missing required field 'action'")
        policy = ActionPolicy.from_dict(data)
        out[policy.action] = policy
    return out
