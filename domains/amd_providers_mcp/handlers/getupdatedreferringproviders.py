"""amd_providers_get_updated_referring_providers - getupdatedreferringproviders.

Doc source: knowledge/reference/amd_api/providers/getupdatedproviders.md
  (sibling section: "Sibling: getupdatedreferringproviders")

Returns ONLY cardinality + group-bys (Aaron 2026-06-04):
- ``count``: total.
- ``by_specialty``: ``{specialty: count}``.
- ``full_pull``: True when ``since`` is empty (bootstrap path).

`since` is OPTIONAL — empty triggers the FULL referring-provider list.
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


ACTION = "getupdatedreferringproviders"
WRITE_ACTION = False
TIER = 1
PERMITTED_ACTIONS = ("getupdatedreferringproviders",)


def _flatten_refprovider(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "refprovider_id": row.get("id", "") or child_text.get("id", ""),
        "name": row.get("name", "") or child_text.get("name", ""),
        "code": row.get("code", ""),
        "specialty": row.get("specialty", ""),
        "practicename": row.get("practicename", ""),
    }


def _sort_key(p: dict[str, str]) -> tuple[str,]:
    return (p.get("refprovider_id") or "",)


async def handle(*, since: str = "") -> dict[str, Any]:
    client = get_client()
    kwargs: dict[str, Any] = {}
    if since:
        kwargs["since"] = since
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", **kwargs,
    )
    if err is not None:
        return {"since": since, "full_pull": not bool(since),
                **err}
    raw_rows = extract_rows_by_tag(raw_dict, "refprovider")
    providers = [_flatten_refprovider(r) for r in raw_rows]
    providers.sort(key=_sort_key)
    # Aaron 2026-06-04: NO raw list, NO raw AMD blob. Delta-sync feed.
    return {
        "since": since,
        "full_pull": not bool(since),
        "count": len(providers),
        "by_specialty": summarize_by(providers, "specialty"),
    }
