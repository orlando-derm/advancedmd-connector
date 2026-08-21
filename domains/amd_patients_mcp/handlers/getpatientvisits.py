"""amd_patients_get_patient_visits — AMD getpatientvisits action.

Doc source: knowledge/reference/amd_api/visits/getpatientvisits.md
(in the visits subtree because that's where the docs live; the action
is part of the patients domain in our split because input is per-patient.)

Returns ONLY pre-computed cardinality + group-bys (Aaron 2026-06-04:
"it cannot do any math or aggregations properly"):
- ``count``: number of visits in the response.
- ``by_provider``: ``{provider_name: count}``.
- ``by_facility``: ``{facility_name: count}``.
- ``by_apptstatus``: ``{apptstatus: count}``.
- ``by_year``: ``{YYYY: count}`` — answers "how many visits in 2025?"
  with one dict lookup.

Internal sort: ``(starttime, visit_id)`` ascending — chronological
history (used only for the by_year derivation; the list itself is
not emitted).
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


ACTION = "getpatientvisits"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getpatientvisits",)


def _flatten_visit(row: dict) -> dict[str, str]:
    """Normalize one raw visit row into the canonical flat shape."""
    child_text = row.get("_child_text") or {}
    child_attrs = row.get("_child_attrs") or {}
    pat_attrs = child_attrs.get("patient") or {}
    return {
        "visit_id": row.get("id", "") or row.get("appointment_id", ""),
        "starttime": (
            row.get("starttime", "")
            or row.get("appointment_datetime", "")
        ),
        "duration": row.get("duration", ""),
        "apptstatus": row.get("apptstatus", "") or row.get("status", ""),
        "provider_id": row.get("providerid", "") or child_text.get("provider_id", ""),
        "provider_name": row.get("provider", "") or child_text.get("provider", ""),
        "facility_id": row.get("facilityid", ""),
        "facility_name": row.get("facility", ""),
        "profile": row.get("profile", "") or row.get("columnheading", ""),
        "profile_id": row.get("profileid", ""),
        "reason": row.get("reason", ""),
        "patient_id": pat_attrs.get("id", ""),
        "patient_name": pat_attrs.get("name", ""),
        "chart_number": pat_attrs.get("chart", ""),
    }


def _sort_key(v: dict[str, str]) -> tuple[str, str]:
    vid = v.get("visit_id") or ""
    try:
        vid_part = (f"{int(vid):020d}",)[0]
    except (TypeError, ValueError):
        vid_part = vid
    return (v.get("starttime") or "", vid_part)


def _by_year(visits: list[dict[str, str]]) -> dict[str, int]:
    """Group visits by YYYY substring of starttime.

    "Starttime is an ISO-prefix string" — first 4 chars are the year
    when present and digit-only; else the visit is grouped under "".
    Empty groups are skipped.
    """
    out: dict[str, int] = {}
    for v in visits:
        st = v.get("starttime") or ""
        if len(st) >= 4 and st[:4].isdigit():
            year = st[:4]
            out[year] = out.get(year, 0) + 1
    return out


async def handle(
    *,
    patient_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    if not patient_id:
        return {"error": "bad_input", "details": {"reason": "patient_id required"}}
    client = get_client()
    # Wire-level rename: Adam-facing `patient_id` -> AMD's `patientid=`
    # (docx line 948: "patientid: (Required) This is the Patient ID").
    # [AARON-REVIEWABLE-DRIFT-3] The Adam-facing catalog schema declares
    # `start_date`/`end_date` parameters with format=date, but the docx
    # Attributes list (lines 948-954) for getpatientvisits does NOT
    # include startdate/enddate — only patientid, appttype, appttypeid,
    # apptstatusid, referral, referringproviderid, referringprovider.
    # AMD would likely fault on "Invalid column name" if these were
    # sent. Dropping them from the wire call until the catalog schema
    # is corrected or a live test confirms they're tolerated. The
    # Adam-facing args remain so existing callers don't break; values
    # are silently ignored at the wire boundary (and echoed in output
    # for traceability).
    kwargs: dict[str, Any] = {"patientid": patient_id}
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", **kwargs,
    )
    if err is not None:
        return {"patient_id": patient_id, **err}
    raw_visits = extract_rows_by_tag(raw_dict, "visit")
    visits = [_flatten_visit(r) for r in raw_visits]
    visits.sort(key=_sort_key)
    # No raw `visits` list and no `raw` blob — Aaron 2026-06-04:
    # "it cannot do any math or aggregations properly." Adam reads
    # only the pre-computed scalars + grouping dicts; the handler is
    # the single source of truth for cardinality.
    return {
        "patient_id": patient_id,
        "count": len(visits),
        "by_provider": summarize_by(visits, "provider_name"),
        "by_facility": summarize_by(visits, "facility_name"),
        "by_apptstatus": summarize_by(visits, "apptstatus"),
        "by_year": _by_year(visits),
    }
