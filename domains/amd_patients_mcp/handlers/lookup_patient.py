"""amd_patients_lookup_patient — AMD lookup action with class=patient.

Doc source: knowledge/reference/amd_api/lookups/ (general lookups doc).

Returns the normalized list-shape envelope (regardless of whether AMD
returned 0, 1, or many candidates):

- ``matches``: stable-sorted list of patient match candidates.
- ``count``: number of matches (0/1/N).
- ``raw``: unmolested AMD response.

Sort key: ``(last_name, first_name, chart_number)`` ascending — the
natural front-desk staff scan order. The sort is stable; AMD's own
return order is preserved within a tied key.
"""
from __future__ import annotations

from typing import Any


from ._common import extract_rows_by_tag, get_client, raw_to_dict, safe_amd_call_async


ACTION = "lookup-patient"  # catalog key (Adam-facing); wire action below
WRITE_ACTION = False
TIER = 3
# Wire action vs catalog action:
#  - Adam's tool name stays `amd_patients_lookup_patient` (catalog key
#    `lookup-patient`).
#  - AMD's wire action is `lookuppatient` (one word, class_=api,
#    name=<search>). The generic `lookup` action with class_=patient
#    that the legacy amd-mcp-server used returns
#    "Encountered an error attempting to create instance of progID:
#    PPMD_patient.patient" on this office key — confirmed live
#    2026-06-04. The docx canonical action is `lookuppatient`.
#  - Only `lookuppatient` is in the allowlist — the legacy shape is
#    dead code and the guard should reject it.
PERMITTED_ACTIONS = ("lookuppatient",)


def _flatten_match(row: dict) -> dict[str, str]:
    child_text = row.get("_child_text") or {}
    return {
        "patient_id": (
            row.get("patient_id", "")
            or row.get("id", "")
            or child_text.get("patient_id", "")
        ),
        "chart_number": (
            row.get("chart_number", "")
            or row.get("chart", "")
            or child_text.get("chart_number", "")
        ),
        "first_name": (
            row.get("first_name", "")
            or child_text.get("first_name", "")
        ),
        "last_name": (
            row.get("last_name", "")
            or child_text.get("last_name", "")
        ),
        "dob": row.get("dob", "") or child_text.get("dob", ""),
    }


def _sort_key(m: dict[str, str]) -> tuple[str, str, str]:
    return (
        (m.get("last_name") or "").lower(),
        (m.get("first_name") or "").lower(),
        m.get("chart_number") or "",
    )


async def handle(*, query: str, page: int = 1) -> dict[str, Any]:
    """Search patients by name/chart with optional paged enumeration.

    `page` is AARON-REVIEWABLE-2 (DUO-11 default): extend in-place
    rather than ship a second tool. AMD's lookup endpoint accepts a
    page parameter; we forward it when >1, otherwise omit so existing
    callers see no behavioral change.
    """
    if not query:
        return {"error": "bad_input", "details": {"reason": "query required"}}
    client = get_client()
    # Live verification 2026-06-04: action="lookuppatient", class_="api",
    # name=<query> returns 10 matches on the production office key.
    # The legacy `action="lookup", class_="patient", search=` pattern
    # (and the intermediate `search=` rewrite from earlier today) BOTH
    # fail with "PPMD_patient.patient instance" errors against the same
    # office key — the docx-canonical action name is the only one that
    # actually works. See knowledge/integrations/amd/patients/
    # lookup-patient.policy.data.json (Adam-facing) for the schema
    # contract.
    call_kwargs = {"class_": "api", "name": query}
    if page and page > 1:
        call_kwargs["page"] = page
    raw_dict, err = await safe_amd_call_async(
        client, action="lookuppatient", raw_to_dict_fn=raw_to_dict,
        **call_kwargs,
    )
    if err is not None:
        return {"query": query, **err}
    raw_rows = extract_rows_by_tag(raw_dict, "patient")
    matches = [_flatten_match(r) for r in raw_rows]
    matches.sort(key=_sort_key)
    # Cap matches at 5. If AMD returned more, set `narrow_query` so Adam
    # tells the user to refine, not try to enumerate. Aaron 2026-06-04:
    # "it cannot do any math or aggregations properly." The handler is
    # the source of truth for `count`; Adam reads it verbatim.
    _MATCH_CAP = 5
    total = len(matches)
    return {
        "query": query,
        "page": page,
        "count": total,
        "matches": matches[:_MATCH_CAP],
        "narrow_query": total > _MATCH_CAP,
    }
