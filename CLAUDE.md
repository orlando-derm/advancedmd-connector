# CLAUDE.md

Guidance for agents working in this repository. SPEC.md is the build
contract and wins over anything here; if this file and SPEC.md disagree,
fix this file.

## What this is

advancedmd-connector is the only process that talks to AdvancedMD. See
README.md for the two-paragraph summary and the architecture diagram.

## Repo map

```
connector/          the connector process itself
  app.py               FastAPI app, routes (POST/GET /v1/tools, /v1/login, /health, /metrics)
  config.py            SPEC 19 environment table, one frozen dataclass
  queues.py            ToolRequest, XmlRequest, entry and request queues
  worker.py            worker loop (SPEC 5.4) -- runs exactly one tool at a time
  sender.py            sender loop, build_xml, parse, send() (SPEC 6) -- ONE OF TWO modules allowed to speak HTTP to AMD
  session.py           login, redirect handling, 1025 recovery, /v1/login check (SPEC 8) -- the OTHER of those two modules
  clock.py             RateClock, tier table, is_peak, persistence (SPEC 7)
  registry.py          tool registry build, verification states (SPEC 9)
  tokens.py            token table, policy, CLI (SPEC 10)
  client_shim.py        AMDClient-shaped facade over send() (Amendment A2) -- what copied handlers call instead of a real client
  audit.py             audit line serializer, key allowlist (SPEC 17.2)
  errors.py             SPEC 14 error classes, one per code
  metrics.py            SPEC 18 metrics
  mcp_surface.py        streamable-HTTP MCP per domain (SPEC 12.2)
  logging_filter.py     SPEC 17.3 redaction filter
  lifecycle.py           startup/shutdown wiring; the only place a real singleton is named
domains/             copied from amd-mcp, package names unchanged -- READ SPEC 6.2 before touching anything here
knowledge/            copied policy files and AMD documentation
advancedmd_mcp/       the published stdio shim package (SPEC 12.3)
plugin/               the Claude Code plugin (SPEC 12.4)
tests/
  unit/ integration/ invariants/ fixtures/ load/
.github/workflows/ci.yml    runs the full suite incl. tests/invariants (SPEC 23.6)
scripts/record_fixture.py   operator-run only, on black-sky, never by an agent (SPEC 23.3)
docs/                  this documentation set
```

## Traversal order

Read in this order before making a change: SPEC.md (the section your
task names), docs/CONNECTOR_DECISIONS.md (why), docs/TOOL_TO_XML_MAP.md
(if the change touches a tool's AMD request shape), then the code.
SPEC.md wins on disagreement; amend CONNECTOR_DECISIONS.md rather than
silently diverging from it.

## Invariants (each one is enforced by a test; do not break them)

- **SPEC 4.4 — no blocking I/O on the event loop.** The sender loop uses
  `httpx.AsyncClient`. Any copied handler code that does blocking I/O
  (file reads, `requests.post`) must be wrapped in `asyncio.to_thread`
  or rewritten. A slow AMD reply must never delay `/health`.
  (`tests/invariants/test_no_blocking_on_loop.py`)
- **SPEC 6.2 — handlers never import httpx, requests, or the AMD URL.**
  Only `connector/sender.py` and `connector/session.py` may speak HTTP
  to AdvancedMD or name an AdvancedMD host. A test parses every file
  under `domains/` and `connector/` with `ast` and fails on any
  forbidden import or URL literal outside those two files.
  (`tests/invariants/test_no_amd_imports_outside_sender.py`)
- **SPEC 17.2 — the audit line accepts only one key set.** `{ts,
  request_id, caller, tool, priority, outcome, amd_calls, amd_actions,
  tier, waited_ms, elapsed_ms, peak, relogin}`. Never args, never
  results, never AMD response bodies, never patient identifiers. The
  serializer in `connector/audit.py` rejects any other key; do not add
  one without also updating this file and SPEC 17.2.
- **SPEC 17.3 — no traceback reaches the stream.** The filter replaces
  `record.exc_info`/`exc_text` with a PHI-free class-name summary, and it
  is attached to uvicorn's own non-propagating handlers too.
  (`tests/unit/test_logging_filter.py`)
- **SPEC 17.4 — AMD transport is HTTPS to an AdvancedMD host.** The login
  redirect target is validated before the credentials are re-posted, and
  a non-https `AMD_BASE_URL` override fails startup.
  (`tests/unit/test_session.py`, `tests/unit/test_scaffold.py`)
- **SPEC 17.4 — no bare host port mapping.** `docker-compose.yml`
  publishes 8820 on one explicit host address, never `"8820:8820"`.
  (`tests/invariants/test_no_public_port_binding.py`)
- **SPEC 23.3 — every fixture is synthetic and says so.**
  (`tests/invariants/test_fixtures_are_synthetic.py`)
- **SPEC 23.6 — connector-side CI invariants.** No httpx/requests import
  and no AMD URL outside `connector/sender.py` and
  `connector/session.py`; no blocking call on the event loop (a test
  injects a slow AMD reply and polls `/health`).

## Never modify domains/ handlers without updating docs/TOOL_TO_XML_MAP.md

`docs/TOOL_TO_XML_MAP.md` is the per-tool ledger of what AMD action/class
each handler sends and its verification state. A handler change that
alters the request shape, the action, the class, or the result shape
without a matching edit to that map leaves the map lying about what the
code does — update both in the same change.

## Other things worth knowing before editing

- Exactly one tool runs at a time (worker loop concurrency 1); exactly
  one AMD request is in flight at a time (sender loop concurrency 1).
  Both are constants in code, not configuration (SPEC 4.5).
- The clock, the session, the token table, and the registry are
  process-wide singletons created once at startup (SPEC 4.6). Never
  construct a second one in request-handling code.
- `connector/client_shim.py` is not a copy of `amd_client/client.py` — it
  is a from-scratch facade with the same method surface, over `send()`.
  See Amendment A2 in docs/CONNECTOR_DECISIONS.md D21.
- No secrets, no real credentials, no PHI, no emojis, anywhere in this
  repo: code, tests, fixtures, docs, or commit messages. Fixtures are
  synthetic only (SPEC 23.3); an agent that needs a new one stops and
  asks the operator.
