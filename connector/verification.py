"""Verification state, SPEC 9.2 and 9.3.

Every tool the connector registers carries a verification state. Only a
verified tool is served: an unverified tool is still LISTED (SPEC 9.2, so
agents can see it exists) but the worker returns ToolUnverified without
running the handler and without spending an AMD call.

The launch set is Appendix A. Nothing else is verified, and nothing here
promotes a tool on its own: a row appears in LAUNCH_SET only after its
request map and result shape are recorded in docs/TOOL_TO_XML_MAP.md.

SPEC 9.3 has five steps. Steps 1, 3, 4 and 5 are satisfied in this repo
(request map from the reference clients, synthetic fixture plus an
Appendix B assertion, tier table, Appendix C defects fixed). Step 2 --
one live call against AdvancedMD by the operator on black-sky returning
success="1" -- is by construction NOT something this build can perform:
no process here may contact AdvancedMD. Each row therefore carries
live_check=PENDING_OPERATOR and `LIVE_CHECK_PENDING` is True for the
whole table. That is recorded honestly rather than claimed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

__all__ = [
    "PENDING_OPERATOR",
    "LIVE_CHECK_PENDING",
    "VerifiedTool",
    "LAUNCH_SET",
    "APPENDIX_A",
    "VerificationTable",
    "default_table",
]

#: SPEC 9.3 step 2 is the operator's live check on black-sky. It is not
#: done, and no agent may do it. Never rewrite this to a date from here.
PENDING_OPERATOR = "PENDING OPERATOR"

#: True while any row still has live_check == PENDING_OPERATOR.
LIVE_CHECK_PENDING = True

_DOC = "docs/TOOL_TO_XML_MAP.md"


@dataclass(frozen=True, slots=True)
class VerifiedTool:
    """One Appendix A row.

    `name` is the canonical registry key (the policy file's tool_name);
    `alias` is the bare AMD action name registered alongside it
    (Amendment D-1 / resolved ambiguity A1).
    """

    name: str
    alias: str
    domain: str
    tier: int
    #: Anchor in docs/TOOL_TO_XML_MAP.md holding the request map and the
    #: Appendix B result shape.
    verification_ref: str
    #: The synthetic fixture the Appendix B test asserts against.
    fixture: str
    #: SPEC 9.3 step 2. Always PENDING_OPERATOR in this repo.
    live_check: str = PENDING_OPERATOR
    write_action: bool = False

    @property
    def verified_at(self) -> str | None:
        """SPEC 9.1 verified_at.

        None while the live check is pending: a date here would assert a
        completed SPEC 9.3, which is exactly what has not happened.
        """
        return None if self.live_check == PENDING_OPERATOR else self.live_check


def _row(
    name: str,
    alias: str,
    domain: str,
    tier: int,
    fixture: str,
    *,
    write_action: bool = False,
) -> VerifiedTool:
    return VerifiedTool(
        name=name,
        alias=alias,
        domain=domain,
        tier=tier,
        verification_ref=f"{_DOC}#verification-ledger-{alias}",
        fixture=f"tests/fixtures/{fixture}",
        write_action=write_action,
    )


#: SPEC Appendix A, keyed by canonical name. "login (internal)" is not a
#: registry tool (Amendment D-4) and is deliberately absent.
LAUNCH_SET: Mapping[str, VerifiedTool] = {
    t.name: t
    for t in (
        _row("amd_patients_get_demographic", "getdemographic",
             "patients", 2, "getdemographic.reply.xml"),
        _row("amd_patients_get_reminder_appts", "getreminderappts",
             "patients", 2, "getreminderappts.reply.xml"),
        _row("amd_visits_get_date_visits", "getdatevisits",
             "visits", 2, "getdatevisits.reply.xml"),
        _row("amd_visits_get_updated_visits", "getupdatedvisits",
             "visits", 1, "getupdatedvisits.reply.xml"),
        _row("amd_patients_lookup_patient", "lookuppatient",
             "patients", 3, "lookuppatient.reply.xml"),
        _row("amd_patients_uploadfile", "uploadfile",
             "patients", 2, "uploadfile.reply.xml", write_action=True),
        _row("amd_ehr_getehrnotes", "getehrnotes",
             "ehr", 2, "getehrnotes.reply.xml"),
        _row("amd_payments_get_tx_history", "gettxhistory",
             "payments", 2, "gettxhistory.reply.xml"),
        _row("amd_billing_get_charge_detail_data", "getchargedetaildata",
             "billing", 2, "getchargedetaildata.reply.xml"),
    )
}

#: Canonical names of the Appendix A launch set, in Appendix A order.
APPENDIX_A: tuple[str, ...] = tuple(LAUNCH_SET)


class VerificationTable:
    """Lookup of verification state by canonical name or by alias."""

    def __init__(self, rows: Mapping[str, VerifiedTool] | None = None) -> None:
        self._by_name: dict[str, VerifiedTool] = dict(
            LAUNCH_SET if rows is None else rows
        )
        self._by_alias: dict[str, VerifiedTool] = {
            row.alias: row for row in self._by_name.values()
        }

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def get(self, name: str) -> VerifiedTool | None:
        row = self._by_name.get(name)
        if row is None:
            row = self._by_alias.get(name)
        return row

    def is_verified(self, name: str) -> bool:
        """SPEC 9.2: verified tools are served, everything else is not."""
        return self.get(name) is not None

    def aliases_for(self, name: str) -> tuple[str, ...]:
        row = self._by_name.get(name)
        return () if row is None else (row.alias,)

    def tier_for(self, name: str, default: int = 3) -> int:
        row = self.get(name)
        return default if row is None else row.tier

    def names(self) -> tuple[str, ...]:
        return tuple(self._by_name)

    def pending_live_checks(self) -> tuple[str, ...]:
        """Rows still waiting on SPEC 9.3 step 2. Reported, never hidden."""
        return tuple(
            name
            for name, row in self._by_name.items()
            if row.live_check == PENDING_OPERATOR
        )


def default_table() -> VerificationTable:
    return VerificationTable()
