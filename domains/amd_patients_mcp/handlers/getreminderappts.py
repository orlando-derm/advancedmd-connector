"""amd_patients_get_reminder_appts — AMD getreminderappts action.

Returns ONLY cardinality + group-bys (Aaron 2026-06-04: "it cannot do
any math or aggregations properly"):
- ``count``: total appointments in the response.
- ``by_remindertype``: ``{remindertype: count}``.
- ``by_provider``: ``{provider_name: count}``.

Internal sort: ``(appointment_datetime, appointment_id)`` ascending —
soonest-due first (used internally only; the list itself is not
emitted).
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any


from ._common import (
    safe_amd_call_async,
    extract_rows_by_tag,
    get_client,
    raw_to_dict,
    summarize_by,
)


ACTION = "getreminderappts"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getreminderappts",)

# All status codes per knowledge/reference/amd_api/enums/appt-status.md.
# AMD's getreminderappts server REQUIRES this attribute despite docx
# listing it as optional (server fault -2147219456 'Missing apptstatus'
# observed by the validator 2026-05-20). Default to the full set so
# Adam gets every reminder; specialized callers can override.
_DEFAULT_APPT_STATUS = "0,1,2,3,5,10,11,12"


def _amd_date_format(iso_or_slash: str) -> str:
    """Normalize an incoming date to AMD's `M/D/YYYY` wire format.

    Adam's tool schema declares `format: date` (ISO 8601 YYYY-MM-DD),
    but AMD's getreminderappts action expects MM/DD/YYYY-shaped strings
    on the `startdate`/`enddate` attributes (docx sample line 1028,
    validator pattern workflows/appointment-validator/src/amd_client/
    client.py:296-307).
    """
    s = (iso_or_slash or "").strip()
    if "/" in s:
        return s
    d = _date.fromisoformat(s)
    return f"{d.month}/{d.day}/{d.year}"


def _flatten_appt(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "appointment_id": row.get("id", "") or row.get("appointment_id", ""),
        "appointment_datetime": (
            row.get("starttime", "")
            or row.get("appointment_datetime", "")
        ),
        "remindertype": (
            row.get("remindertype", "")
            or row.get("type", "")
            or row.get("recalltype", "")
        ),
        "provider_id": row.get("providerid", "") or child_text.get("provider_id", ""),
        "provider_name": row.get("provider", "") or child_text.get("provider", ""),
        "patient_id": row.get("patientid", "") or child_text.get("patient_id", ""),
        "patient_name": child_text.get("first_name", ""),
        "phone_cell": child_text.get("phone_cell", ""),
    }


def _sort_key(a: dict[str, str]) -> tuple[str, str]:
    aid = a.get("appointment_id") or ""
    try:
        aid_part = (f"{int(aid):020d}",)[0]
    except (TypeError, ValueError):
        aid_part = aid
    return (a.get("appointment_datetime") or "", aid_part)


async def handle(
    *,
    start_date: str,
    end_date: str,
    patient_id: str | None = None,
) -> dict[str, Any]:
    if not start_date or not end_date:
        return {
            "error": "bad_input",
            "details": {"reason": "start_date and end_date required"},
        }
    client = get_client()
    # Wire-level rename: Adam-facing `start_date`/`end_date` (ISO 8601)
    # become AMD's `startdate=`/`enddate=` in M/D/YYYY. `apptstatus`
    # is required by the AMD server (see _DEFAULT_APPT_STATUS docstring)
    # and `starttime`/`endtime` bracket the full day window so the
    # caller's date range is honored end-to-end. Mirrors the validator
    # pattern (workflows/appointment-validator/src/amd_client/
    # client.py:296-307).
    try:
        amd_start = _amd_date_format(start_date)
        amd_end = _amd_date_format(end_date)
    except ValueError as exc:
        return {
            "start_date": start_date, "end_date": end_date,
            "error": "bad_input",
            "details": {"reason": f"dates must be YYYY-MM-DD or M/D/YYYY: {exc}"},
        }
    kwargs: dict[str, Any] = {
        "startdate": amd_start, "enddate": amd_end,
        "starttime": "12:00 AM", "endtime": "11:59 PM",
        "apptstatus": _DEFAULT_APPT_STATUS,
    }
    if patient_id:
        # Adam-facing `patient_id` -> AMD wire `patientid`.
        kwargs["patientid"] = patient_id
    raw_dict, err = await safe_amd_call_async(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", **kwargs,
    )
    if err is not None:
        return {"start_date": start_date, "end_date": end_date, **err}
    # AMD may use either <reminder> or <appt> as the row tag; check both.
    raw_rows = extract_rows_by_tag(raw_dict, "reminder")
    if not raw_rows:
        raw_rows = extract_rows_by_tag(raw_dict, "appt")
    appts = [_flatten_appt(r) for r in raw_rows]
    appts.sort(key=_sort_key)
    # Contract (2026-06-04 revision): canonical cardinality is
    # `count`/`by_*` — Adam quotes those verbatim, never recounts. The
    # flat `appts` list is returned so Adam can answer row-level
    # questions ("which patients have appts with provider X tomorrow")
    # by selecting rows where `provider_id` matches. Counting the
    # selection still goes through `by_provider_id[id]`. The raw AMD
    # blob stays omitted — it's redundant once the structured list is
    # here.
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(appts),
        "by_remindertype": summarize_by(appts, "remindertype"),
        "by_provider": summarize_by(appts, "provider_name"),
        "by_provider_id": summarize_by(appts, "provider_id"),
        "appts": appts,
    }
