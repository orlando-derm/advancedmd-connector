"""amd_patients_get_reminder_patient_birthdays — AMD action.

Returns ONLY cardinality (Aaron 2026-06-04: "it cannot do any math or
aggregations properly"). No raw list, no raw AMD blob.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import extract_rows_by_tag, get_client, raw_to_dict

ACTION = "getreminderpatientbirthdays"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getreminderpatientbirthdays",)


def _amd_date_format(iso_or_slash: str) -> str:
    """Normalize ISO 8601 (YYYY-MM-DD) to AMD's M/D/YYYY wire format.

    Mirrors getdatevisits / getreminderrecallvisits / getreminderappts.
    Docx sample line 3232:
    <ppmdmsg action="getreminderpatientbirthdays" ...
             startdate="1/1/2016" enddate="1/31/2016" minage="10"
             maxage="18" />.
    """
    s = (iso_or_slash or "").strip()
    if "/" in s:
        return s
    d = _date.fromisoformat(s)
    return f"{d.month}/{d.day}/{d.year}"


async def handle(*, start_date: str, end_date: str, min_age: Any = None, max_age: Any = None) -> dict[str, Any]:
    if not start_date or not end_date:
        return {"error": "bad_input", "details": {"reason": "start_date and end_date required"}}
    client = get_client()
    # Wire-level rename: Adam-facing start_date/end_date (ISO 8601)
    # become AMD's `startdate=`/`enddate=` in M/D/YYYY. Python-style
    # min_age/max_age become wire-style `minage`/`maxage` per docx
    # lines 3248-3249.
    try:
        amd_start = _amd_date_format(start_date)
        amd_end = _amd_date_format(end_date)
    except ValueError as exc:
        return {
            "start_date": start_date, "end_date": end_date,
            "error": "bad_input",
            "details": {"reason": f"dates must be YYYY-MM-DD or M/D/YYYY: {exc}"},
        }
    call_kwargs: dict[str, Any] = {"startdate": amd_start, "enddate": amd_end}
    if min_age not in (None, ""):
        call_kwargs["minage"] = str(min_age)
    if max_age not in (None, ""):
        call_kwargs["maxage"] = str(max_age)
    raw_dict, err = safe_amd_call(client, action="getreminderpatientbirthdays", raw_to_dict_fn=raw_to_dict, **call_kwargs)
    if err is not None:
        return {"start_date": start_date, "end_date": end_date, **err}
    # AMD may use <patient> or <reminder> as the row tag.
    rows = extract_rows_by_tag(raw_dict, "patient")
    if not rows:
        rows = extract_rows_by_tag(raw_dict, "reminder")
    # Aaron 2026-06-04: NO raw list, NO raw AMD blob. Birthdays carry
    # patient names + DOBs (PHI). Adam only needs the cardinality.
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(rows),
    }
