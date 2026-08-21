"""Shared test fixtures. Every later lane builds on these.

Two rules hold everywhere in this suite:

1. No real sleeping and no wall-clock nondeterminism. Time is injected
   (`fake_clock`), so a test that exercises SPEC 5.3 aging or SPEC 7.3
   pacing runs in microseconds and asserts on exact numbers.
2. No PHI. Fixture trees here are synthetic and hand-written from the
   reference clients' XML shapes.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

REPO_ROOT = Path(__file__).resolve().parent.parent
# domains/ packages import each other by their original top-level names
# (amd_mcp_common, amd_patients_mcp, ...), unchanged per SPEC N1.
for path in (str(REPO_ROOT), str(REPO_ROOT / "domains")):
    if path not in sys.path:
        sys.path.insert(0, path)

from connector.client_shim import AMDClient  # noqa: E402
from connector.config import Config  # noqa: E402
from connector.interfaces import Caller, RegistryEntry  # noqa: E402
from connector.queues import (  # noqa: E402
    PRIORITY_BATCH,
    PRIORITY_INTERACTIVE,
    EntryQueue,
    RequestQueue,
    ToolRequest,
)

SYNTHETIC_NOTE = (
    "synthetic fixture - hand-written from reference client XML shapes, "
    "contains no real patient data"
)


# --------------------------------------------------------------- clock


class FakeClock:
    """An injectable monotonic clock. Nothing in the suite sleeps.

    Also serves as a fake RateClock: `acquire` records the tier and
    returns immediately, so pacing is asserted by inspecting `acquired`
    rather than by waiting.
    """

    def __init__(self, start: float = 1000.0) -> None:
        self._t = float(start)
        self.acquired: list[int | str] = []
        self.peak = False
        self.flushed = 0
        self.limits: dict[str, dict[str, int]] = {
            "1": {"used": 0, "limit": 0},
            "2": {"used": 0, "limit": 10},
            "3": {"used": 0, "limit": 21},
            "login": {"used": 0, "limit": 1},
        }

    # time source
    def __call__(self) -> float:
        return self._t

    def monotonic(self) -> float:
        return self._t

    def advance(self, seconds: float) -> float:
        self._t += float(seconds)
        return self._t

    def advance_ms(self, milliseconds: float) -> float:
        return self.advance(milliseconds / 1000.0)

    # RateClock protocol
    async def acquire(self, tier: int | str) -> None:
        self.acquired.append(tier)
        key = str(tier)
        if key in self.limits:
            self.limits[key]["used"] += 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in self.limits.items()}

    def is_peak(self) -> bool:
        return self.peak

    def flush(self) -> None:
        self.flushed += 1


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


# ------------------------------------------------------------- session


class FakeSession:
    """A Session that never touches the network. SPEC 8 shape only."""

    def __init__(self, state: str = "ok") -> None:
        self.token = "synthetic-usercontext-token" if state == "ok" else None
        self.endpoint = "https://example.invalid/synthetic-endpoint"
        self.state = state
        self.last_login_at = "2026-01-01T00:00:00+00:00" if state == "ok" else None
        self.age_s = 0.0 if state == "ok" else None
        self.logins: list[bool] = []
        self.fail_next = False

    async def login(self, force: bool = False) -> None:
        self.logins.append(force)
        if self.fail_next:
            from connector.errors import SessionFailed

            self.state = "degraded"
            self.token = None
            raise SessionFailed()
        self.state = "ok"
        self.token = "synthetic-usercontext-token"
        self.age_s = 0.0


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


# ---------------------------------------------------------- fixture XML


def synthetic_reply(inner: str = "<patientlist/>") -> Any:
    """A minimal successful AMD reply tree.

    Shape (<PPMDResults><Results success="1">...) is taken from the
    reference clients' parse path. No PHI: ids are obviously synthetic.
    """
    xml = (
        f"<!-- {SYNTHETIC_NOTE} -->"
        '<PPMDResults><Results success="1">'
        f"{inner}"
        "</Results></PPMDResults>"
    )
    return etree.fromstring(xml.encode("utf-8"))


def synthetic_fault(code: str = "1025", description: str = "Session has timed out") -> Any:
    """A failing AMD reply tree, for the SPEC 6.4 fault path."""
    xml = (
        f"<!-- {SYNTHETIC_NOTE} -->"
        '<PPMDResults><Results success="0">'
        f'<Error Code="{code}" Description="{description}"/>'
        "</Results></PPMDResults>"
    )
    return etree.fromstring(xml.encode("utf-8"))


@pytest.fixture
def fixture_tree() -> Any:
    return synthetic_reply()


class FakeSender:
    """A send() that fills slots from a canned tree instead of AMD.

    Records every XmlRequest it was given, so tests assert the request
    shape (action, class, attrs, children) without any network.
    """

    def __init__(self, reply: Any | None = None) -> None:
        self.reply = reply if reply is not None else synthetic_reply()
        self.sent: list[Any] = []
        self.raise_next: BaseException | None = None

    async def __call__(self, req: Any) -> Any:
        self.sent.append(req)
        if self.raise_next is not None:
            exc, self.raise_next = self.raise_next, None
            raise exc
        if callable(self.reply):
            return self.reply(req)
        return self.reply

    @property
    def actions(self) -> list[str]:
        return [r.action for r in self.sent]


@pytest.fixture
def fake_send() -> FakeSender:
    return FakeSender()


@pytest.fixture
def amd_client(fake_send: FakeSender) -> AMDClient:
    return AMDClient(fake_send, record_id="00000000-0000-4000-8000-000000000000")


# -------------------------------------------------------------- tokens


class FakeTokenTable:
    """A synthetic token table. The plaintexts here are not secrets and
    match nothing real; they exist so policy tests can be written."""

    def __init__(self, callers: dict[str, Caller] | None = None) -> None:
        self._by_token: dict[str, Caller] = callers or {
            "test-interactive-token": Caller(
                name="test-interactive",
                priority=PRIORITY_INTERACTIVE,
                phi=False,
                tools="*",
                max_queue=100,
            ),
            "test-batch-token": Caller(
                name="test-batch",
                priority=PRIORITY_BATCH,
                phi=True,
                tools=("getdemographic", "getreminderappts"),
                max_queue=500,
            ),
            "test-revoked-token": Caller(
                name="test-revoked",
                priority=PRIORITY_INTERACTIVE,
                revoked="2026-01-01",
            ),
        }
        self.reloads = 0

    def lookup(self, plaintext: str) -> Caller | None:
        caller = self._by_token.get(plaintext)
        if caller is None or caller.is_revoked:
            return None
        return caller

    def allows(self, caller: Caller, entry: RegistryEntry) -> bool:
        if entry.write_action and entry.name not in caller.may_write:
            return False
        if caller.tools == "*":
            return True
        allowed = set(caller.tools)
        return bool(allowed.intersection(entry.names))

    def redact(self, caller: Caller) -> bool:
        return not caller.phi

    def reload_if_changed(self) -> bool:
        self.reloads += 1
        return False


@pytest.fixture
def token_table() -> FakeTokenTable:
    return FakeTokenTable()


@pytest.fixture
def caller(token_table: FakeTokenTable) -> Caller:
    return token_table.lookup("test-interactive-token")


# --------------------------------------------------------- queues, cfg


@pytest.fixture
def entry_queue(fake_clock: FakeClock) -> EntryQueue:
    return EntryQueue(cap=2000, batch_aging_ms=60000, monotonic=fake_clock)


@pytest.fixture
def request_queue() -> RequestQueue:
    return RequestQueue()


@pytest.fixture
def make_record(fake_clock: FakeClock):
    """Build a ToolRequest on the injected clock."""

    def _make(
        tool: str = "getdemographic",
        *,
        caller: str = "test-interactive",
        priority: int = PRIORITY_INTERACTIVE,
        args: dict[str, Any] | None = None,
        max_wait_ms: int = 20000,
        arrived_at: float | None = None,
    ) -> ToolRequest:
        return ToolRequest(
            tool=tool,
            args=dict(args or {}),
            caller=caller,
            priority=priority,
            arrived_at=fake_clock() if arrived_at is None else arrived_at,
            max_wait_ms=max_wait_ms,
        )

    return _make


BASE_ENV = {
    "AMD_USERNAME": "placeholder-user",
    "AMD_PASSWORD": "placeholder-password",
    "AMD_OFFICE_KEY": "PLACEHOLDER",
    "CONNECTOR_TOKENS_PATH": "/data/tokens.json",
}


@pytest.fixture
def base_env() -> dict[str, str]:
    """A minimal valid environment. Placeholder values only."""
    return dict(BASE_ENV)


@pytest.fixture
def config(base_env: dict[str, str]) -> Config:
    from connector.config import load_config

    return load_config(base_env)


@pytest.fixture
def registry_entry() -> RegistryEntry:
    return RegistryEntry(
        name="amd_patients_get_demographic",
        domain="patients",
        handler=None,
        schema={"type": "object", "properties": {"patient_id": {"type": "string"}}},
        write_action=False,
        tier=2,
        verified=True,
        verified_at="2026-01-01",
        verification_ref="docs/TOOL_TO_XML_MAP.md#getdemographic",
        aliases=("getdemographic",),
    )


__all__ = ["FakeClock", "FakeSession", "FakeSender", "FakeTokenTable",
           "synthetic_reply", "synthetic_fault", "replace"]
