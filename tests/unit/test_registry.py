"""The tool registry, SPEC 9.1 / 9.2 / 16.1 step 4.

These tests build the REAL registry from the nine copied domain
packages. Nothing is mocked out: if a policy file, a generated schema or
a handler module goes missing, this is where it shows up.
"""
from __future__ import annotations

import pytest

from connector.interfaces import Caller, RegistryEntry
from connector.registry import (
    DOMAIN_PACKAGES,
    RegistryBuildError,
    ToolRegistry,
    build_registry,
    default_tier_for,
)
from connector.verification import (
    APPENDIX_A,
    LAUNCH_SET,
    PENDING_OPERATOR,
    VerificationTable,
)


@pytest.fixture(scope="module")
def registry() -> ToolRegistry:
    return build_registry()


# ------------------------------------------------------------ build


def test_all_nine_domains_are_registered(registry):
    domains = {entry.domain for entry in registry}

    assert domains == {domain for domain, _pkg in DOMAIN_PACKAGES}
    assert len(DOMAIN_PACKAGES) == 9


def test_every_appendix_a_tool_is_present_and_verified(registry):
    """SPEC 9.4: the launch set is served; everything else is not."""
    for name in APPENDIX_A:
        entry = registry.get(name)
        assert entry is not None, name
        assert entry.verified is True, name

    assert set(registry.verified_names()) == set(APPENDIX_A)


def test_a_missing_appendix_a_tool_fails_the_build(monkeypatch):
    """SPEC 16.1 step 4: refuse to start rather than serve a partial set."""
    with pytest.raises(RegistryBuildError) as excinfo:
        build_registry(require=(*APPENDIX_A, "amd_patients_not_a_tool"))

    assert "amd_patients_not_a_tool" in str(excinfo.value)


def test_a_broken_domain_names_the_domain_and_nothing_else():
    with pytest.raises(RegistryBuildError) as excinfo:
        build_registry(domains=(("patients", "not_a_real_package"),), require=())

    assert "patients" in str(excinfo.value)


# ---------------------------------------------------------- aliases


def test_alias_and_canonical_name_resolve_to_one_entry(registry):
    """Amendment D-1 / resolved ambiguity A1."""
    for name, row in LAUNCH_SET.items():
        canonical = registry.get(name)
        alias = registry.get(row.alias)
        assert canonical is alias, name
        assert row.alias in canonical.aliases


def test_canonical_names_carry_no_aliases(registry):
    """SPEC 12.1 parity: MCP tools/list advertises canonical names only."""
    names = registry.canonical_names()

    assert len(names) == len(set(names)) == len(registry)
    for alias in registry.aliases():
        assert alias not in names


def test_lookup_patient_alias_is_the_wire_action_not_the_catalog_key(registry):
    """The policy key is lookup-patient; AMD's action is lookuppatient."""
    entry = registry.get("amd_patients_lookup_patient")

    assert entry.aliases == ("lookuppatient",)
    assert registry.get("lookuppatient") is entry


# ----------------------------------------------------- verification


def test_unverified_tools_are_still_listed(registry):
    """SPEC 9.2: agents can see a tool exists before it is promoted."""
    unverified = [e for e in registry if not e.verified]

    assert len(unverified) > 0
    assert len(registry) == len(unverified) + len(APPENDIX_A)
    assert all(e.verification_ref is None for e in unverified)


def test_verified_at_stays_none_while_the_live_check_is_pending():
    """SPEC 9.3 step 2 belongs to the operator; nothing here may claim it."""
    table = VerificationTable()

    assert set(table.pending_live_checks()) == set(APPENDIX_A)
    for row in LAUNCH_SET.values():
        assert row.live_check == PENDING_OPERATOR
        assert row.verified_at is None


def test_every_verified_entry_points_at_its_ledger_entry(registry):
    for name in APPENDIX_A:
        entry = registry.get(name)
        assert entry.verification_ref.startswith("docs/TOOL_TO_XML_MAP.md#")


# ------------------------------------------------------------ tiers


def test_appendix_a_tiers_match_the_spec(registry):
    expected = {
        "amd_patients_get_demographic": 2,
        "amd_patients_get_reminder_appts": 2,
        "amd_visits_get_date_visits": 2,
        "amd_visits_get_updated_visits": 1,
        "amd_patients_lookup_patient": 3,
        "amd_patients_uploadfile": 2,
        "amd_ehr_getehrnotes": 2,
        "amd_payments_get_tx_history": 2,
        "amd_billing_get_charge_detail_data": 2,
    }

    assert {name: registry.get(name).tier for name in expected} == expected


def test_getupdatedvisits_is_tier_1_everywhere():
    """SPEC Appendix C defect 4, in the tier rule and in the copied policy."""
    import json
    from pathlib import Path

    policy = json.loads(
        (Path(__file__).resolve().parents[2]
         / "knowledge/integrations/amd/visits/getupdatedvisits.policy.data.json")
        .read_text(encoding="utf-8")
    )

    assert policy["tier"] == 1
    assert default_tier_for("getupdatedvisits") == 1


def test_tier_rule_defaults(registry):
    """SPEC 7.4: getupdated* -> 1, everything unlisted -> 3."""
    assert default_tier_for("getupdatedreferringproviders") == 1
    assert default_tier_for("lookupcarrier") == 3
    assert default_tier_for("") == 3


def test_an_injected_tier_table_wins():
    """connector/clock.py owns the table; the registry only consumes it."""
    registry = build_registry(tier_for=lambda action: 3)

    assert registry.get("amd_visits_get_updated_visits").tier == 3


# ------------------------------------------------------ write tools


def test_write_tools_are_registered_but_flagged(registry):
    upload = registry.get("amd_patients_uploadfile")

    assert upload.write_action is True
    assert upload.verified is True
    assert len([e for e in registry if e.write_action]) > 1


# ----------------------------------------------------------- listing


def test_list_filters_to_the_caller_allowlist(registry):
    caller = Caller(name="c", priority=0, tools=("getdemographic",))

    listed = registry.list(caller)

    assert [e.name for e in listed] == ["amd_patients_get_demographic"]
    assert len(registry.list()) == len(registry)
    assert len(registry.list(Caller(name="c", priority=0))) == len(registry)


def test_duplicate_names_are_refused():
    def entry(name: str, alias: str) -> RegistryEntry:
        return RegistryEntry(name=name, domain="patients", handler=None,
                             schema={}, aliases=(alias,))

    with pytest.raises(RegistryBuildError):
        ToolRegistry([entry("a", "shared"), entry("b", "shared")])
