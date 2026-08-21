"""amd_patients_get_updated_patients — AMD getupdatedpatients.

Doc source: knowledge/reference/amd_api/patients/getupdatedpatients.md

Returns ONLY:
- ``count``: number of patient rows in the response.

No ``by_*`` dimensions: the updated-patients feed is intentionally
minimal — the AMD response carries little more than `patient_id` +
`lastupdated`. Per the decision file: keep enrichment narrow.

Aaron 2026-06-04: NO raw list, NO raw AMD blob. "it cannot do any math
or aggregations properly." Nightly cron hits AMD directly; Adam only
needs the cardinality.
"""
from __future__ import annotations

from typing import Any

from amd_mcp_common.errors import safe_amd_call

from ._common import extract_rows_by_tag, get_client, raw_to_dict


ACTION = "getupdatedpatients"
WRITE_ACTION = False
TIER = 2
PERMITTED_ACTIONS = ("getupdatedpatients",)


def _flatten_patient(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "patient_id": (
            row.get("id", "")
            or row.get("patient_id", "")
            or child_text.get("patient_id", "")
        ),
        "chart_number": row.get("chart_number", "") or row.get("chart", ""),
        "lastupdated": row.get("lastupdated", "") or row.get("dtlast", ""),
    }


def _sort_key(p: dict[str, str]) -> tuple[str,]:
    pid = p.get("patient_id") or ""
    try:
        return (f"{int(pid):020d}",)
    except (TypeError, ValueError):
        return (pid,)


async def handle(*, since: str, limit: int = 100) -> dict[str, Any]:
    client = get_client()
    raw_dict, err = safe_amd_call(
        client, action=ACTION, raw_to_dict_fn=raw_to_dict,
        class_="api", since=since, limit=str(limit),
    )
    if err is not None:
        return {"since": since, "limit": limit, **err}
    raw_rows = extract_rows_by_tag(raw_dict, "patient")
    patients = [_flatten_patient(r) for r in raw_rows]
    patients.sort(key=_sort_key)
    # No raw `patients` list and no `raw` blob — Aaron 2026-06-04:
    # "it cannot do any math or aggregations properly." Delta-sync feed
    # consumers (nightly cron) hit AMD directly; Adam only needs the
    # cardinality. If a downstream feature needs per-patient detail,
    # that feature should call lookup_patient or getdemographic.
    return {
        "since": since,
        "limit": limit,
        "count": len(patients),
    }
