"""Settings (lifted from legacy amd-mcp-server with new common fields).

New fields beyond the legacy:

  - ``domain``: per-server slug for self-identification ("patients",
    "visits", etc.). Passed in at boot, used in audit-v2 records.
  - ``amd_mcp_rate_limit_backend``: in_memory / file_locked /
    in_memory_divided.
  - ``amd_mcp_limiter_state_dir``: where the file-locked limiter
    persists its buckets.
  - ``amd_mcp_domain_count``: peer-count for in_memory_divided.
  - ``knowledge_root``: workspace knowledge/ dir, used by
    knowledge_loader to find per-action policy files.
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_TRUTHY = {"1", "true", "yes", "on"}


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def _resolve_office_key() -> tuple[str | None, bool]:
    new_val = os.environ.get("AMD_OFFICE_KEY")
    legacy = os.environ.get("AMD_OFFICE_CODE")
    if new_val:
        return new_val, False
    if legacy:
        return legacy, True
    return None, False


def _workspace_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "knowledge").is_dir() and (parent / "runtime").is_dir():
            return parent
    return Path.cwd()


def _resolve_hash_key() -> bytes:
    """Per-install HMAC key for the PHI redactor.

    Precedence: env var; persisted file; generate + persist; in-memory
    only if persistence fails.
    """
    env_val = os.environ.get("AMD_MCP_HASH_KEY")
    if env_val:
        try:
            key = bytes.fromhex(env_val.strip())
            if len(key) >= 16:
                return key
        except ValueError:
            pass
    state_dir = _workspace_root() / "runtime" / "state" / "amd-mcp"
    state_dir.mkdir(parents=True, exist_ok=True)
    keyfile = state_dir / "hash-key.bin"
    if keyfile.exists():
        try:
            return bytes.fromhex(keyfile.read_text().strip())
        except (OSError, ValueError):
            pass
    fresh = secrets.token_bytes(32)
    try:
        keyfile.write_text(fresh.hex())
    except OSError:
        pass
    return fresh


@dataclass
class Settings:
    """Runtime configuration for a per-domain MCP server."""

    # AMD auth.
    amd_username: str | None = None
    amd_password: str | None = None
    amd_office_key: str | None = None
    amd_app_name: str = "TEMP"
    amd_base_url: str | None = None

    # Server behaviour.
    allow_phi: bool = False
    hash_key: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    cache_ttl_sec: int = 3600
    log_level: str = "INFO"

    # New common fields.
    domain: str = "common"
    amd_mcp_rate_limit_backend: str = "in_memory"
    amd_mcp_limiter_state_dir: Path | None = None
    amd_mcp_domain_count: int = 1
    knowledge_root: Path = field(default_factory=lambda: _workspace_root() / "knowledge")

    # Internal flags.
    used_legacy_office_code: bool = False

    @classmethod
    def from_env(cls, *, domain: str = "common") -> "Settings":
        office_key, used_legacy = _resolve_office_key()
        try:
            cache_ttl = int(os.environ.get("AMD_MCP_CACHE_TTL_SEC", "3600"))
        except ValueError:
            cache_ttl = 3600
        try:
            domain_count = int(os.environ.get("AMD_MCP_DOMAIN_COUNT", "1"))
        except ValueError:
            domain_count = 1
        limiter_state_dir_env = os.environ.get("AMD_MCP_LIMITER_STATE_DIR")
        limiter_state_dir = (
            Path(limiter_state_dir_env) if limiter_state_dir_env else None
        )
        settings = cls(
            amd_username=os.environ.get("AMD_USERNAME"),
            amd_password=os.environ.get("AMD_PASSWORD"),
            amd_office_key=office_key,
            amd_app_name=os.environ.get("AMD_APP_NAME", "TEMP"),
            amd_base_url=os.environ.get("AMD_BASE_URL"),
            allow_phi=_is_truthy(os.environ.get("AMD_MCP_ALLOW_PHI")),
            hash_key=_resolve_hash_key(),
            cache_ttl_sec=cache_ttl,
            log_level=os.environ.get("AMD_MCP_LOG_LEVEL", "INFO"),
            domain=domain,
            amd_mcp_rate_limit_backend=os.environ.get(
                "AMD_MCP_RATE_LIMIT_BACKEND", "in_memory"
            ),
            amd_mcp_limiter_state_dir=limiter_state_dir,
            amd_mcp_domain_count=domain_count,
            knowledge_root=_workspace_root() / "knowledge",
            used_legacy_office_code=used_legacy,
        )
        if used_legacy:
            logging.getLogger("amd_mcp_common.config").warning(
                "AMD_OFFICE_CODE is the legacy name; please migrate to AMD_OFFICE_KEY."
            )
        return settings

    def require_amd_credentials(self) -> None:
        missing = []
        if not self.amd_username:
            missing.append("AMD_USERNAME")
        if not self.amd_password:
            missing.append("AMD_PASSWORD")
        if not self.amd_office_key:
            missing.append("AMD_OFFICE_KEY (or AMD_OFFICE_CODE)")
        if missing:
            raise RuntimeError(
                f"Missing required AMD environment variables: {', '.join(missing)}"
            )

    @property
    def runtime_root(self) -> Path:
        return _workspace_root() / "runtime"


_settings: Settings | None = None


def get_settings(*, domain: str = "common") -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env(domain=domain)
    return _settings


def reset_settings_for_tests() -> None:
    global _settings
    _settings = None
