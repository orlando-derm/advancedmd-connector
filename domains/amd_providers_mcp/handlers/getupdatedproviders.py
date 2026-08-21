"""amd_providers_get_updated_providers - AMD getupdatedproviders action.

Doc source: knowledge/reference/amd_api/providers/getupdatedproviders.md
Providers added/modified/deleted since a servertime checkpoint (Tier 1).

Returns ONLY pre-computed cardinality + group-bys (Aaron 2026-06-04):
- ``count``: total providers in the response.
- ``by_updatestatus``: ``{updatestatus: count}`` — natural for a
  delta-sync feed (e.g., "C" = changed, "N" = new, "D" = deleted).
- ``by_specialty``: ``{specialty: count}`` when AMD returns specialty.
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import (
    extract_rows_by_tag,
    get_client,
    raw_to_dict,
    summarize_by,
)


ACTION = "getupdatedproviders"
WRITE_ACTION = False
TIER = 1
PERMITTED_ACTIONS = ("getupdatedproviders",)


def _flatten_provider(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "provider_id": row.get("id", "") or child_text.get("provider_id", ""),
        "name": row.get("name", "") or child_text.get("name", ""),
        "code": row.get("code", ""),
        "npi": row.get("npi", ""),
        "specialty": row.get("specialty", ""),
        "updatestatus": row.get("updatestatus", ""),
        "changedat": row.get("changedat", ""),
        "createdat": row.get("createdat", ""),
    }


def _sort_key(p: dict[str, str]) -> tuple[str,]:
    pid = p.get("provider_id") or ""
    try:
        return (f"{int(pid):020d}",)
    except (TypeError, ValueError):
        return (pid,)


async def handle(*, since: str, include_profiles: bool = False) -> dict[str, Any]:
    if not since:
        return {"error": "bad_input", "details": {"reason": "since required"}}
    client = get_client()
    kwargs: dict[str, Any] = {"since": since}
    if include_profiles:
        kwargs["include_profiles"] = True
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", **kwargs,
    )
    if err is not None:
        return {"since": since, "include_profiles": include_profiles,
                **err}
    raw_rows = extract_rows_by_tag(raw_dict, "provider")
    providers = [_flatten_provider(r) for r in raw_rows]
    providers.sort(key=_sort_key)
    # Aaron 2026-06-04: NO raw list, NO raw AMD blob. Delta-sync feeds
    # are nightly-cron territory; Adam only needs the cardinality +
    # group-bys. "it cannot do any math or aggregations properly."
    return {
        "since": since,
        "include_profiles": include_profiles,
        "count": len(providers),
        "by_updatestatus": summarize_by(providers, "updatestatus"),
        "by_specialty": summarize_by(providers, "specialty"),
    }
