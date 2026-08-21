"""amd_providers_lookup_provider - AMD lookupprovider action.

Doc source: knowledge/reference/amd_api/lookups/overview.md.

Provider name search via the dedicated `lookupprovider` action. Cheaper
than a full roster pull for one-off resolution. Tier 3.

Returns:
- ``matches``: stable-sorted list of provider candidates.
- ``count``: total matches.
- ``by_specialty``: ``{specialty: count}``.
- ``raw``: unmolested AMD response.
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


ACTION = "lookupprovider"
WRITE_ACTION = False
TIER = 3
PERMITTED_ACTIONS = ("lookupprovider",)


def _flatten_match(row: dict) -> dict[str, str]:
    return {
        "provider_id": row.get("id", ""),
        "name": row.get("name", ""),
        "code": row.get("code", ""),
        "npi": row.get("npi", ""),
        "specialty": row.get("specialty", ""),
    }


def _sort_key(p: dict[str, str]) -> tuple[str, str]:
    return ((p.get("name") or "").lower(), p.get("provider_id") or "")


async def handle(
    *,
    name: str = "",
    exact_match: bool = False,
    page: int = 1,
) -> dict[str, Any]:
    """Provider roster.

    Returns the full provider roster (one cheap tier-3 AMD call;
    practices typically have <100 providers) with all identifier
    shapes — `provider_id`, `name` (LAST,FIRST), short `code` (e.g.
    "VBMD"), NPI, specialty. The LLM picks the matching row using
    whatever judgment a human would (nicknames, titles, abbreviations,
    "the dermatologist", a typed code). No server-side filter, no
    match cap — the handler doesn't try to guess which row the user
    meant. The `name`/`exact_match`/`page` arguments are accepted for
    backwards compatibility but the handler ignores `name`/`exact_match`
    (they were a 2026-06-04 over-correction that silently hid rows
    when the query didn't substring-match the LAST,FIRST name field).
    """
    if page < 1:
        return {
            "error": "bad_input",
            "details": {"reason": "page must be >= 1"},
        }
    client = get_client()
    # Always pull the full roster — pass empty name= so AMD returns
    # everything. Single call per query; if this becomes hot, the
    # rate limiter + a short TTL cache in _common.py is the right
    # next step (not in scope for this fix).
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api",
        name="",
        exactmatch="0",
        page=str(page),
    )
    if err is not None:
        return {"name": name, "exact_match": exact_match, "page": page,
                **err}
    raw_rows = extract_rows_by_tag(raw_dict, "provider")
    roster = [_flatten_match(r) for r in raw_rows]
    roster.sort(key=_sort_key)
    return {
        "name": name,
        "exact_match": exact_match,
        "page": page,
        "count": len(roster),
        "by_specialty": summarize_by(roster, "specialty"),
        "providers": roster,
    }
