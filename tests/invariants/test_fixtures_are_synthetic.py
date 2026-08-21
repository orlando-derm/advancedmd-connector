"""SPEC 23.3 / 23.6: every fixture is synthetic, and provably so.

Two rules, both enforced on every file under tests/fixtures/:

  (a) the file carries the exact provenance line, so a recording that
      skipped the operator review cannot be committed silently;
  (b) no SSN / phone / email / date-of-birth shaped value appears outside
      the sanctioned synthetic placeholders below.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

PROVENANCE = (
    "synthetic fixture - hand-written from reference client XML shapes, "
    "contains no real patient data"
)

#: The only identity-shaped values a fixture may contain. Anything else
#: matching a PHI shape is a real value until proven otherwise.
SANCTIONED = frozenset({
    "000-00-0000",       # SSN placeholder
    "000-000-0000",      # phone placeholder
    "555-0100",          # phone placeholder used by the recorder
    "1/1/1900",          # DOB placeholder
    "1/1/1970",          # DOB placeholder used by the recorder
    "00000",             # zip placeholder
})

SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
DOB = re.compile(r"(?i)\b(?:dob|birth[a-z]*)\s*=\s*\"([^\"]*)\"")


def fixture_files() -> list[Path]:
    return sorted(p for p in FIXTURES.rglob("*") if p.is_file() and p.name != "README.md")


def test_the_fixture_directory_is_not_empty():
    assert fixture_files()


@pytest.mark.parametrize("path", fixture_files(), ids=lambda p: p.name)
def test_every_fixture_carries_the_provenance_line(path: Path):
    assert PROVENANCE in path.read_text(encoding="utf-8"), (
        f"{path.name} is missing the exact SPEC 23.3 provenance line"
    )


@pytest.mark.parametrize("path", fixture_files(), ids=lambda p: p.name)
def test_no_fixture_carries_an_unsanctioned_identity_value(path: Path):
    text = path.read_text(encoding="utf-8")
    found: list[str] = []
    for pattern in (SSN, PHONE):
        found.extend(m for m in pattern.findall(text) if m not in SANCTIONED)
    for address in EMAIL.findall(text):
        domain = address.rsplit("@", 1)[-1].lower()
        if not (domain.endswith(".invalid") or domain.endswith(".example")
                or domain == "example.com"):
            found.append(address)
    for value in DOB.findall(text):
        if value.strip() and value.strip() not in SANCTIONED:
            found.append(value)
    assert not found, f"{path.name} carries identity-shaped values: {sorted(set(found))}"
