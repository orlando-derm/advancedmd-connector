"""Schema loader: reads emitted JSON Schemas with an LRU cache.

Used by per-domain MCP servers at boot:

    schema = schema_loader.load(domain="patients", action="getdemographic")
    # schema is the Draft 2020-12 dict, ready to attach to a Tool spec.

The loader walks two trees in order of preference:

1. `amd-mcp-server-common/schemas/generated/<domain>/<action>.json`
   — machine output (catalog or WSDL).
2. `amd-mcp-server-common/schemas/manual/<domain>/<action>.json`
   — hand-written for actions not yet catalogued / not in WSDL.

Falls through to a clear FileNotFoundError naming both attempted paths
if neither exists.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


def _common_root() -> Path:
    """Locate amd-mcp-server-common's root.

    1. AMD_MCP_COMMON_ROOT env var (explicit override; tests use this).
    2. Walk parents from this file looking for the pyproject.toml.
    """
    override = os.environ.get("AMD_MCP_COMMON_ROOT")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists() and parent.name == "amd-mcp-server-common":
            return parent
    # Fallback: assume two levels up from this file (src/amd_mcp_common/).
    return here.parent.parent.parent


def _candidate_paths(domain: str, action: str) -> tuple[Path, Path]:
    root = _common_root()
    return (
        root / "schemas" / "generated" / domain / f"{action}.json",
        root / "schemas" / "manual" / domain / f"{action}.json",
    )


@lru_cache(maxsize=256)
def load(domain: str, action: str) -> dict:
    """Load one schema. Cached per (domain, action)."""
    generated, manual = _candidate_paths(domain, action)
    if generated.exists():
        return json.loads(generated.read_text(encoding="utf-8"))
    if manual.exists():
        return json.loads(manual.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"No schema for domain={domain!r} action={action!r}. "
        f"Tried:\n  {generated}\n  {manual}"
    )


def cache_clear() -> None:
    """Drop the LRU cache. Tests call this between runs."""
    load.cache_clear()


def list_domain_actions(domain: str) -> list[str]:
    """List every (generated or manual) action in a domain.

    Useful for boot-time validation: domain server compares this with
    its policy files to detect missing schemas / extra policies.
    """
    root = _common_root()
    actions: set[str] = set()
    for sub in ("generated", "manual"):
        d = root / "schemas" / sub / domain
        if d.is_dir():
            for f in d.glob("*.json"):
                actions.add(f.stem)
    return sorted(actions)
