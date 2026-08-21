"""amd_visits_get_date_visits - AMD getdatevisits action.

Doc source: knowledge/reference/amd_api/visits/getdatevisits.md
Visits for a single calendar date on the office key.

Returns BOTH:
- ``visits``: a flat, stable-sorted list of visit records with the
  fields the chatbot actually needs. The LLM should report from this,
  not from ``raw``.
- ``count``: total number of visits (so the LLM never has to count).
- ``by_provider``: ``{provider_id: count}`` so "how many did X see?"
  is a dict lookup, not a head-filter.
- ``raw``: the unmolested AMD response, for debugging.

Sort key: ``(starttime, visit_id)``. ``getdatevisits`` historically
omits time-of-day in the default template; when starttime is empty
the rows still sort stably by visit_id.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any

from lxml import etree


from ._common import get_client, raw_to_dict, safe_amd_call_async, summarize_by


ACTION = "getdatevisits"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getdatevisits",)


def _amd_date_format(iso_or_slash: str) -> str:
    """Normalize an incoming date to AMD's `M/D/YYYY` wire format.

    Adam's tool schema declares `format: date` (ISO 8601 YYYY-MM-DD),
    but AMD's getdatevisits action expects MM/DD/YYYY-shaped strings on
    the `visitdate` attribute. Confirmed against the validator's working
    pattern (workflows/appointment-validator/src/amd_client/client.py:238)
    and live-tested on the 2021 doc.

    Accepts the canonical ISO shape; passes through anything that
    already contains '/' so callers in tests can hand in the wire
    format directly.
    """
    s = (iso_or_slash or "").strip()
    if "/" in s:
        return s
    d = _date.fromisoformat(s)
    return f"{d.month}/{d.day}/{d.year}"


# Template children for the visitlist response. Without these, AMD
# returns rows with empty attributes — Adam then sees nothing useful
# from a 20-row schedule. See validator pattern
# (amd_client/client.py:239-246). The attribute name on the left of
# each "..." is the column AMD will populate; the right-hand string
# is the human-readable label echoed back on the row.
def _template_children() -> list:
    # IMPORTANT (2026-06-05 — my second attempt got this wrong):
    # `getdatevisits` rejects providerid/provider/facilityid/facility/
    # reason/profile/profileid as requested columns with HTTP 400
    # "Invalid column name." Documented in the validator at
    # workflows/appointment-validator/src/amd_client/client.py:270-274,
    # confirmed live 2026-05-20. Those attributes ARE valid on
    # `getupdatedvisits` — just not here. AMD returns providerid /
    # provider on the visit row by default for this action, so the
    # extractor reads them from `attrs` without needing to request.
    # If by_provider comes back empty, it's NOT a missing request —
    # it's a data issue (the practice's visits genuinely lack the
    # field) or an extraction-key mismatch. Do NOT re-add them here.
    return [
        etree.Element(
            "visit", columnheading="ColumnHeading", duration="Duration",
            color="Color", apptstatus="ApptStatus",
        ),
        etree.Element("patient", name="Name", chart="Chart"),
        etree.Element("insurance", carname="CarName", carcode="CarCode"),
    ]
    # 2026-06-05 (REVERTED): adding starttime="StartTime" to the visit
    # element broke the AMD call — handler returned an error envelope
    # (no `visits` key), classifier passthroughed it, Adam saw zero
    # visits. AMD's accepted/rejected template columns for getdatevisits
    # need real investigation (see runtime/scratchpad/amd-tools-discovery/
    # amd_api_doc.txt section on getdatevisits) before retrying. The
    # validator's amd_client.py:351 parses starttime from response rows
    # of a DIFFERENT action (getreminderappts), so starttime IS valid
    # there — just not as an opt-in column on getdatevisits.


def _extract_visits(raw_dict: Any) -> list[dict[str, str]]:
    """Walk the raw_to_dict tree and pull <visit> child elements out.

    Each visit becomes a flat dict of its attributes plus a nested
    ``patient`` dict for the patient child if present. Defensive
    against missing keys — empty string fallback everywhere.
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
            for child in node.get("_children") or []:
                if isinstance(child, dict) and child.get("_tag") == "patient":
                    pat_attrs = dict(child.get("_attrs") or {})
                    break
            out.append({
                "visit_id": attrs.get("id", ""),
                "starttime": attrs.get("starttime", ""),
                "duration": attrs.get("duration", ""),
                "apptstatus": attrs.get("apptstatus", ""),
                "provider_id": attrs.get("providerid", ""),
                "provider_name": attrs.get("provider", ""),
                "facility_id": attrs.get("facilityid", ""),
                "facility_name": attrs.get("facility", ""),
                "profile": attrs.get("profile", "") or attrs.get("columnheading", ""),
                "profile_id": attrs.get("profileid", ""),
                "reason": attrs.get("reason", ""),
                "patient_id": pat_attrs.get("id", ""),
                "patient_name": pat_attrs.get("name", ""),
                "chart_number": pat_attrs.get("chart", ""),
            })
            return
        for child in node.get("_children") or []:
            _walk(child)

    _walk(raw_dict)
    return out


def _sort_key(v: dict[str, str]) -> tuple[str, str]:
    # starttime may be ""; visit_id sorts numerically when present.
    vid = v.get("visit_id") or ""
    try:
        vid_part = (f"{int(vid):020d}",)[0]
    except (TypeError, ValueError):
        vid_part = vid
    return (v.get("starttime") or "", vid_part)


async def handle(*, date: str) -> dict[str, Any]:
    if not date:
        return {"error": "bad_input", "details": {"reason": "date required"}}
    client = get_client()
    try:
        amd_date = _amd_date_format(date)
    except ValueError as exc:
        return {
            "date": date,
            "error": "bad_input",
            "details": {"reason": f"date must be YYYY-MM-DD or M/D/YYYY: {exc}"},
        }
    raw_dict, err = await safe_amd_call_async(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", visitdate=amd_date,
        children=_template_children(),
    )
    if err is not None:
        return {"date": date, **err}
    visits = _extract_visits(raw_dict)
    visits.sort(key=_sort_key)
    # Contract (2026-06-04 revision): the canonical cardinality fields
    # (`count`, `by_*`) are the source of truth for counting and
    # grouping — Adam quotes them verbatim and never recounts. The flat
    # `visits` list is returned so Adam can answer row-level questions
    # (e.g. "which patients does provider X have today", "what time is
    # patient Y's appointment") by selecting rows where the relevant
    # field matches. Counting that selection still routes through the
    # canonical aggregation (e.g. `by_provider_id[id]`), not
    # `len(filtered_list)`. The `raw` AMD blob stays omitted — it's
    # redundant once the structured list is here.
    return {
        "date": date,
        "count": len(visits),
        "by_provider": summarize_by(visits, "provider_name"),
        "by_provider_id": summarize_by(visits, "provider_id"),
        "by_profile": summarize_by(visits, "profile"),
        "by_facility": summarize_by(visits, "facility_name"),
        "by_facility_id": summarize_by(visits, "facility_id"),
        "by_apptstatus": summarize_by(visits, "apptstatus"),
        "visits": visits,
    }
