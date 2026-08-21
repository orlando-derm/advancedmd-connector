"""amd_visits_get_updated_visits - AMD getupdatedvisits action.

Doc source: knowledge/reference/amd_api/visits/getupdatedvisits.md
Visits updated since a timestamp (delta-sync friendly).

Returns ONLY pre-computed cardinality + group-bys (Aaron 2026-06-04:
"it cannot do any math or aggregations properly"):
- ``count``: total number of visits (so the LLM never has to count).
- ``by_provider``: ``{provider_name: count}`` so "how many for X?" is a
  dict lookup, not a head-filter.
- ``by_facility``: ``{facility_name: count}``.
- ``by_apptstatus``: ``{apptstatus: count}`` — the natural status
  dimension for a delta-sync feed.

Sort key (primary): ``lastupdated`` desc when present (newest first is
the natural delta-sync ordering); falls back to ``starttime`` then
``visit_id``. The ``getupdatedvisits`` AMD doc lists ``lastupdated``
as the canonical attribute on each row; mirror that ordering so
consumers can read the head of the list as "freshest updates first".
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import get_client, raw_to_dict, summarize_by


ACTION = "getupdatedvisits"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getupdatedvisits",)


def _extract_visits(raw_dict: Any) -> list[dict[str, str]]:
    """Walk the raw_to_dict tree and pull <visit> child elements out.

    Each visit becomes a flat dict of its attributes plus a nested
    ``patient`` dict for the patient child if present. Mirrors
    ``getdatevisits._extract_visits`` shape with the additional
    ``lastupdated`` field unique to the updated-feed.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(raw_dict, dict):
        return out

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("_tag") == "visit":
            attrs = dict(node.get("_attrs") or {})
            pat_attrs: dict[str, str] = {}
            children = node.get("_children") or []
            child_text: dict[str, str] = {}
            for child in children:
                if not isinstance(child, dict):
                    continue
                if child.get("_tag") == "patient":
                    pat_attrs = dict(child.get("_attrs") or {})
                    continue
                tag = child.get("_tag")
                text = child.get("_text")
                if tag and text:
                    child_text[tag] = text
            # Tolerant of both attr-style ("provider="...") and
            # child-element-style (<provider_id>...</provider_id>) shapes.
            out.append({
                "visit_id": attrs.get("id", "") or attrs.get("appointment_id", ""),
                "starttime": attrs.get("starttime", "") or attrs.get("appointment_datetime", ""),
                "lastupdated": attrs.get("lastupdated", "") or attrs.get("dtlast", ""),
                "duration": attrs.get("duration", ""),
                "apptstatus": attrs.get("apptstatus", "") or attrs.get("status", ""),
                "provider_id": attrs.get("providerid", "") or child_text.get("provider_id", ""),
                "provider_name": attrs.get("provider", "") or child_text.get("provider", ""),
                "facility_id": attrs.get("facilityid", ""),
                "facility_name": attrs.get("facility", ""),
                "profile": attrs.get("profile", "") or attrs.get("columnheading", ""),
                "profile_id": attrs.get("profileid", ""),
                "reason": attrs.get("reason", ""),
                "patient_id": pat_attrs.get("id", "") or child_text.get("patient_id", ""),
                "patient_name": pat_attrs.get("name", ""),
                "chart_number": pat_attrs.get("chart", ""),
            })
            return
        for child in node.get("_children") or []:
            _walk(child)

    _walk(raw_dict)
    return out


def _sort_key(v: dict[str, str]) -> tuple[str, str, str]:
    # lastupdated DESC is the natural delta-sync ordering. Python sort
    # is ascending by default — invert via negation-of-ord trick: we
    # sort the negated string by returning lastupdated under a "high
    # first" reflection. Simpler: just sort ascending and reverse the
    # list at the call site. Use ascending key here.
    vid = v.get("visit_id") or ""
    try:
        vid_part = (f"{int(vid):020d}",)[0]
    except (TypeError, ValueError):
        vid_part = vid
    return (
        v.get("lastupdated") or "",
        v.get("starttime") or "",
        vid_part,
    )


async def handle(*, since: str, limit: int = 100) -> dict[str, Any]:
    if not since:
        return {"error": "bad_input", "details": {"reason": "since required"}}
    client = get_client()
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", since=since, limit=str(limit),
    )
    if err is not None:
        return {"since": since, "limit": limit, **err}
    visits = _extract_visits(raw_dict)
    # Sort ascending then reverse so the head of the list is the most
    # recent update (typical delta-sync consumer expectation).
    visits.sort(key=_sort_key)
    visits.reverse()
    return {
        "since": since,
        "limit": limit,
        "count": len(visits),
        "by_provider": summarize_by(visits, "provider_name"),
        "by_provider_id": summarize_by(visits, "provider_id"),
        "by_facility": summarize_by(visits, "facility_name"),
        "by_facility_id": summarize_by(visits, "facility_id"),
        "by_apptstatus": summarize_by(visits, "apptstatus"),
        "visits": visits,
    }
