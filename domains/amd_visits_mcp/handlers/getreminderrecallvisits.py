"""amd_visits_get_reminder_recall_visits - AMD getreminderrecallvisits action.

Doc source: knowledge/reference/amd_api/visits/getreminderrecallvisits.md
Recall visits for a date range with optional cap.

Returns:
- ``recalls``: a flat, stable-sorted list of recall records.
- ``count``: total number of recalls (so the LLM never has to count).
- ``by_remindertype``: ``{remindertype: count}`` — the natural dimension
  for a recall feed (e.g., 6-month, 1-year follow-up).
- ``by_provider``: ``{provider_name: count}``.

Sort key: ``(recall_date, recall_id)`` ascending — soonest-due first.

Aaron 2026-06-04: NO raw list, NO raw AMD blob. Adam reads only the
pre-computed cardinality + grouping dicts. "it cannot do any math or
aggregations properly."
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import get_client, raw_to_dict, summarize_by


ACTION = "getreminderrecallvisits"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getreminderrecallvisits",)


def _amd_date_format(iso_or_slash: str) -> str:
    """Normalize an incoming date to AMD's `M/D/YYYY` wire format.

    Adam's tool schema declares `format: date` (ISO 8601 YYYY-MM-DD),
    but AMD's getreminderrecallvisits action expects MM/DD/YYYY-shaped
    strings on the `startdate`/`enddate` attributes. Confirmed against
    docx sample (line 1116:
    <ppmdmsg action="getreminderrecallvisits" ...
             startdate="1/3/2016" enddate="1/9/2016" maxrecalls="10" />).

    Accepts the canonical ISO shape; passes through anything that
    already contains '/' so callers in tests can hand in the wire
    format directly.
    """
    s = (iso_or_slash or "").strip()
    if "/" in s:
        return s
    d = _date.fromisoformat(s)
    return f"{d.month}/{d.day}/{d.year}"


def _extract_recalls(raw_dict: Any) -> list[dict[str, str]]:
    """Walk the raw_to_dict tree and pull <recall> child elements out.

    Tolerant of both attr-style and child-element-style AMD shapes.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(raw_dict, dict):
        return out

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("_tag") == "recall":
            attrs = dict(node.get("_attrs") or {})
            children = node.get("_children") or []
            child_text: dict[str, str] = {}
            pat_attrs: dict[str, str] = {}
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
            out.append({
                "recall_id": attrs.get("id", "") or attrs.get("appointment_id", ""),
                "recall_date": attrs.get("recall_date", "") or attrs.get("recalldate", ""),
                "remindertype": (
                    attrs.get("remindertype", "")
                    or attrs.get("type", "")
                    or attrs.get("recalltype", "")
                ),
                "provider_id": attrs.get("providerid", "") or child_text.get("provider_id", ""),
                "provider_name": attrs.get("provider", "") or child_text.get("provider", ""),
                "patient_id": pat_attrs.get("id", "") or child_text.get("patient_id", ""),
                "patient_name": pat_attrs.get("name", ""),
                "chart_number": pat_attrs.get("chart", ""),
            })
            return
        for child in node.get("_children") or []:
            _walk(child)

    _walk(raw_dict)
    return out


def _sort_key(r: dict[str, str]) -> tuple[str, str]:
    rid = r.get("recall_id") or ""
    try:
        rid_part = (f"{int(rid):020d}",)[0]
    except (TypeError, ValueError):
        rid_part = rid
    return (r.get("recall_date") or "", rid_part)


async def handle(
    *,
    start_date: str,
    end_date: str,
    max_recalls: int | None = None,
) -> dict[str, Any]:
    if not start_date or not end_date:
        return {
            "error": "bad_input",
            "details": {"reason": "start_date and end_date required"},
        }
    client = get_client()
    # Wire-level rename: Adam-facing `start_date`/`end_date` (ISO 8601
    # per the action catalog `format: date`) become AMD's `startdate=`
    # and `enddate=` in M/D/YYYY. `max_recalls` becomes `maxrecalls`.
    # See _amd_date_format docstring for the docx citation.
    try:
        amd_start = _amd_date_format(start_date)
        amd_end = _amd_date_format(end_date)
    except ValueError as exc:
        return {
            "start_date": start_date, "end_date": end_date,
            "error": "bad_input",
            "details": {"reason": f"dates must be YYYY-MM-DD or M/D/YYYY: {exc}"},
        }
    kwargs: dict[str, Any] = {"startdate": amd_start, "enddate": amd_end}
    if max_recalls is not None:
        kwargs["maxrecalls"] = str(max_recalls)
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", **kwargs,
    )
    if err is not None:
        return {
            "start_date": start_date, "end_date": end_date,
            "max_recalls": max_recalls, **err,
        }
    recalls = _extract_recalls(raw_dict)
    recalls.sort(key=_sort_key)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "max_recalls": max_recalls,
        "count": len(recalls),
        "by_remindertype": summarize_by(recalls, "remindertype"),
        "by_provider": summarize_by(recalls, "provider_name"),
        "by_provider_id": summarize_by(recalls, "provider_id"),
        "recalls": recalls,
    }
