# AMD Connector Cutover: Locked Decisions

Status: LOCKED 2026-08-20 (design conversation, pre-build). Supersedes
amd-mcp-server-common/memory/decisions/2026-06-03-cross-process-rate-limit.md
(which rejected a central daemon for v1).

## D1. One process talks to AdvancedMD
A new service, amd-advancedmd-connector (service amd-dispatcher) (internal port 8820, same Coolify compose
project), holds the single AMD login/session. No other container or backend
service opens an AMD socket or holds AMD credentials.

## D2. The tool call is the only request shape
Every request into advancedmd-connector, whether from an AI via an MCP server or
from a backend workflow via the SDK, is a tool call:

    {"tool": "getdemographic", "args": {"patient_id": "12345"}, "max_wait_ms": 30000}
    -> {"ok": true, "result": {...}, "meta": {"waited_ms", "amd_calls", "tier"}}

advancedmd-connector hosts the tool registry (the existing domain handler packages)
and translates tool -> one or more AMD XML requests. Nobody outside the
dispatcher sees ppmdmsg, usercontext, msgtime, class names, or the AMD URL.

## D3. Tool exposure to agents is unchanged
Per-action tool schemas, policy files, the write gate
(WRITE_TOOLS_ENABLED=False), and PHI redaction for AI callers stay as they
are. Only what happens after a tool call is received changes.

## D4. Two queues, serial tools, clocked XML
- tool queue: priority (interactive > batch), FIFO within priority, not
  clocked. The worker pops one tool, runs it to completion, returns the
  result, then pops the next. max_wait_ms applies to time in this queue only.
- xml queue: clocked. Each AMD request waits for a free slot in its tier's
  sliding 60-second window (tier tables from rate_limit.py). Login is an XML
  request too: tier 1, top priority, through the clock.
- A tool that fails mid-way fails whole; no partial results.
- Every XML request carries its tool's priority tag from day one so that
  priority-ordered XML service (two tools in flight) can be added later
  without restructuring. Not built now.

## D5. Fairness comes from small tools
Tools should map to few XML requests. Range/loop behaviour lives in the SDK
on the caller side (one tool call per day, etc.) so each call re-enters the
tool queue and interactive calls interleave. Existing tools that loop
internally are flagged in docs/TOOL_TO_XML_MAP.md.

## D6. Return shape: JSON dict, SDK converts to existing dataclasses
advancedmd-connector returns the handler's serialized dict. lib/advancedmd_connector in
orlando-derm-backend keeps the workflows' existing method names
(get_patient_bundle, get_appointments_via_reminders, get_updated_visits,
search_patients_by_name, uploadfile, get_chart_files) as thin wrappers that
call the tool and build the same dataclasses (PatientBundle, VisitRecord)
the workflows use today. Verified by field-by-field comparison against the
vendored clients on saved AMD responses. note-audit's raw-note path uses a
raw flag on its token.

## D7. One token per app; policy derives from the token
ADVANCEDMD_CONNECTOR_URL + ADVANCEDMD_CONNECTOR_TOKEN per app. The token, not a field in
the body, determines: caller identity, default priority (interactive:
admin-console, chatbot; batch: validator, srt-auths, note-audit, intake),
allow_phi (workflows yes, AI callers no), raw_xml (note-audit), and the
write allowlist (uploadfile: intake only; default deny).

## D8. admin-console login is a forwarded-credential check
/v1/login accepts user-submitted credentials, performs a metered throwaway
login (tier 1 via the clock), returns ok/not ok. It does not reuse or
replace advancedmd-connector's main session.

## D9. MCP containers become forwarders
Domain MCP servers keep their SSE ports (8801-8809) and tool schemas, stop
constructing AMDClient, and forward each tool call to advancedmd-connector.

## D10. Gaps to close in Phase 1
- lookuppatient has no tool; add a handler (patients domain).
- uploadfile exists only as a write-gated stub in amd-mcp; patient-intake's
  vendored implementation is the reference.

## Out of scope (unchanged)
Python package renames; collapsing the 9 MCP ports; amd-portal-mcp
(Playwright).

## D11. Name: advancedmd-connector
GitHub repo, Coolify app and local folder are renamed amd-mcp ->
advancedmd-connector (not amd-connector). Backend library is
lib/advancedmd_connector/. Env vars are ADVANCEDMD_CONNECTOR_URL and
ADVANCEDMD_CONNECTOR_TOKEN. The compose service is still amd-dispatcher and
domain subfolders keep their amd-*-mcp names.

## D12. Tool registry is verified-or-refused
docs/TOOL_TO_XML_MAP.md (2026-08-20) shows many generated handlers call
client.call without class_ and with non-AMD attribute names; they raise
TypeError before reaching AMD. advancedmd-connector registers every tool but only
serves tools marked verified (proven action, class, attrs, templates); an
unverified tool returns a clear "tool not verified" error. The backend's
vendored clients are the reference XML for the 9 workflow actions
(getreminderappts, getdemographic, getupdatedvisits, lookuppatient,
uploadfile, getehrnotes, gettxhistory, getchargedetaildata, getdatevisits).
Known defects to fix in Phase 1: getdemographic chart_number path,
getmaster_patient patient_id attr name, missing class_ across ehr/
masterfiles/system/providers/codes handlers.

## D13. Internal structure: two queues, two loops, slots all the way down
Locked 2026-08-20 after walkthrough.

Entry side
- Each incoming HTTP request gets its own receiver (one FastAPI handler
  call, bound to that request's connection). The receiver looks up the
  token, builds a ToolRequest record {tool, args, caller, priority,
  arrived, max_wait_ms, reply: Future}, puts it in the entry queue, and
  awaits record.reply. The record carries no address; the receiver holds
  the connection.
- One worker loop pops the entry queue (priority, then arrival), refuses
  records past max_wait_ms, looks the tool up in REGISTRY, runs the tool
  function with record.args, writes an audit line (ids and counts only),
  and set_result/set_exception on record.reply. One record at a time.

AMD side
- Tool functions never contact AdvancedMD. They build XmlRequest objects
  {action, class_, attrs, children, tier, priority, reply: Future} and call
  send(req), which puts the object in the request queue and awaits
  req.reply.
- One sender loop owns the RateClock and the single AMD session. It pops
  the request queue, awaits clock.wait_for_slot(tier), logs in if needed
  (tier 1, through the clock), builds the XML, posts it, parses the reply,
  handles session-expired by one re-login and resend, and fills req.reply.
- The request queue is a real queue even though serial tools mean it holds
  at most one item today; this is what allows priority-ordered service and
  two tools in flight later without restructuring.

Dependencies
- Dependent AMD requests inside a tool are sequenced by the tool's own
  line order: the second send() is not created until the first returned.
  The queue needs no dependency logic.
- Independent requests (for example one per day) may be submitted together
  and awaited together; the clock still paces them.

Return path
- Every answer climbs back through the chain it came down: sender loop
  fills req.reply -> send returns to the tool -> tool returns to the worker
  -> worker fills record.reply -> receiver returns over its connection.
  Nothing selects a destination at any step.

Naming
- "advancedmd-connector" is the program workflows and MCP forwarders talk
  to. The compose service name stays amd-dispatcher; in prose use
  advancedmd-connector.

## D14. Rate clock parameters (from AMD API Documentation, "API Usage Restrictions")
Per office key, sliding 60-second window, limit looked up at each send from
the current Mountain time (peak = Mon-Fri 06:00-18:00 MT):
  tier 1 (GETUPDATEDVISITS, GETUPDATEDPATIENTS): 1/min peak, 60/min off-peak
  tier 2 (GETDEMOGRAPHIC, GETDATEVISITS, GETTXHISTORY, GETAPPTS, SAVECHARGES,
          UPDVISITWITHNEWCHARGES, GETPAYMENTDETAILDATA): 12/min peak, 120 off-peak
  tier 3 (all LOOKUP*, anything unlisted): 24/min peak, 120 off-peak
Exceeding any tier in a one-minute interval bills $0.01 per excess call.
Run at 90% of each cap. Login is its own tier-1 bucket (observed ~1 per 60 s
per account; AMD returns 429 beyond that). Reuse rate_limit.py tables and
is_peak(). Fix: getupdatedvisits is tier 2 in code/policy but tier 1 per
AMD; the clock pins tiers from AMD's list, not from handler constants.

## D15. Session recovery
AMD publishes no session length; expiry is signalled by fault 1025 /
-2147220479 "Session has timed out". Recovery happens inside the sender
loop while it still holds the failed request: log in again (through the
clock, tier-1 login bucket), resend the same request once, fill its slot,
continue. No requeue and no explicit clock pause are needed because the
loop is serial. If the resend also returns 1025, or login is refused, the
request fails with a clear error; never loop. Proactive refresh is deferred
until the audit log shows 1025 landing on interactive calls.

## D16. New repository, amd-mcp untouched (supersedes Phase 0 rename and D11's rename clause)
advancedmd-connector is a new repo, new Coolify project, new local folder.
amd-mcp and its nine containers on 8801-8809 are not modified; they keep
serving until every consumer has moved, then they are stopped. The nine
domain packages, policies, schemas, redaction, and write gate are copied
into the new repo unchanged (package names kept).

## D17. MCP distribution (supersedes D9's forwarder containers)
Agents attach one of two ways, both backed by POST /v1/tools:
- remote: the connector serves MCP over streamable HTTP at /mcp/<domain>
  and /mcp/all on its single port, bearer token in headers;
- local: a published stdio package `advancedmd-mcp` (uvx advancedmd-mcp
  --domain patients) that forwards to ADVANCEDMD_CONNECTOR_URL with
  ADVANCEDMD_CONNECTOR_TOKEN; no credentials, no tool logic.
The repo ships a Claude Code plugin (plugin/.claude-plugin/plugin.json +
.mcp.json) declaring the nine stdio servers; the same files serve as
Cursor/Desktop config. Tool names, schemas, and redacted shapes are
identical across remote, local, and today's amd-mcp.
See SPEC.md for the full contract.

## D18. Integration decisions (P2)
Recorded here because each one resolves a seam or a conflict that no
single lane owned.

- Startup entry point. `connector.lifecycle.wire_real_deps(config)` is
  the only place a real singleton is named; `connector.app.build_app()`
  is the production ASGI factory and the container runs
  `uvicorn --factory connector.app:build_app`. Importing connector.app
  therefore reads no environment and opens no file.
- MCP session idle timeout is configuration, not a constant:
  MCP_SESSION_IDLE_S (SPEC 15, default 3600) joins the SPEC 19 table and
  is passed to mount_mcp.
- SPEC 7.6 per-caller pacing is carried on the request, not looked up:
  ToolRequest gains `caller_limit` (set by the receiver from the token's
  per_minute) and XmlRequest gains `caller` and `caller_limit`, which the
  sender hands to clock.acquire. Nothing below the receiver ever resolves
  a caller.
- SPEC 5.3 aging versus SPEC 23.5 fairness. Promoting a whole aged batch
  backlog at once satisfies "batch cannot starve" and breaks "every
  interactive call starts within one tool's duration": records that
  arrived together promote together and, being older, sort ahead of every
  later interactive call. So promotion is bounded twice: at most ONE
  promoted record is outstanding, and a promoted record is keyed on the
  moment it was promoted rather than on its original arrived_at.
  `arrived_at` itself is never rewritten. See
  connector/queues.py::EntryQueue._promote_aged and
  tests/load/test_fairness.py.
- One login at a time. AmdSession.login holds a lock and re-checks under
  it. Without it the startup login and the first tool call each take a
  slot from the 1/min login bucket and the loser waits a full minute for
  a session it was about to be handed.
- GET /v1/tools and the MCP surface build their row with the same
  function (connector.mcp_surface.tool_row), so the SPEC 12.4 parity test
  cannot be satisfied by two copies drifting apart.
- Metrics are fed from the audit line's own fields
  (lifecycle._AuditingMetrics): a value the SPEC 17.2 key set forbids in
  an audit line cannot reach a public /metrics label either.

## D19. Tailnet-only transport (accepted risk)
The connector binds to the Docker compose network and the Tailscale
interface only; it has no public port (SPEC 17.4). Transport inside the
tailnet is WireGuard-encrypted by Tailscale, and version 1 adds no TLS
termination on top of that. This is an accepted risk, not an oversight:
the condition attached to accepting it is that the tailnet remains the
only route to the connector. If that ever stops being true — a public
port is added, or the connector becomes reachable from outside the
tailnet by any other means — TLS termination inside the tailnet (SPEC
25) is no longer deferrable and must be built before that route ships.
/health and /metrics are unauthenticated but are covered by the same
condition: their exposure is safe only because they are unreachable from
outside the tailnet.

## D20. The login-check cache (SPEC 8.7)
/v1/login (the admin-console forwarded-credential check) shares the
connector's 1-per-minute login bucket with the connector's own session
login, through a separate, throwaway AmdSession that never touches the
connector's session. Sharing the bucket means concurrent staff logins
serialize behind it — the second one waits up to 60 s. The mitigation is
an in-memory cache, keyed on sha256(username + office_key + password),
of successful checks for LOGIN_CHECK_CACHE_S (default 300 s); a cache
hit consumes no login-bucket slot. The password itself is never in the
cache, never logged, and never written to disk in any form — only the
digest and an expiry timestamp are held, and only in memory. The cache
is cleared on every restart, so a fresh process re-pays one login-bucket
slot per distinct credential it checks until its own cache warms back
up.

## D21. Clock persistence across restart (SPEC 7.5)
The rate clock writes its bucket state (wall-clock epoch timestamps, not
monotonic ones, since monotonic time is meaningless across a restart) to
CLOCK_STATE_PATH on every acquire, off the event loop via
asyncio.to_thread so the write can never block a send. On startup it
loads that file and honors any timestamp still under 60 s old, replaying
it into the new process's monotonic frame by the wall-clock offset
between the write and the load. A missing or unreadable file is treated
as "the previous process's spend this minute is unknown," which means
every bucket starts as if it were already full for a full 60 s window —
the conservative direction, because a restart that let a new process
believe its buckets were empty could double a minute's actual sends
against AdvancedMD's cap and its $0.01-per-excess-call billing. The
session itself is deliberately not persisted the same way: it is
memory-only and a restart always re-logs-in, which is why two restarts
inside one minute produce a self-healing degraded start (SPEC 16.3)
rather than a clock violation.

## D22. Two ambiguity resolutions, recorded (A1, A2)
Both are binding for this build; this entry exists so they are findable
from the decisions file rather than only from the build brief that
resolved them.

- **A1 — canonical tool_name plus Appendix A bare-action aliases.**
  Appendix A and SPEC 10.4 name AMD actions bare (e.g. getdemographic);
  the policy files copied from amd-mcp expose namespaced tool names
  (e.g. amd_patients_get_demographic). The policy tool_name is the
  canonical registry key. Each Appendix A tool additionally registers
  its bare AMD action name as an alias resolving to the same registry
  entry. Token `tools` allowlists and `may_write` accept either
  spelling. GET /v1/tools lists the canonical name plus an `aliases`
  list; MCP tools/list advertises canonical names only, which is what
  keeps SPEC 12.1 parity with today's amd-mcp servers intact.
- **A2 — amd_client is not vendored; client_shim.py is the facade.**
  The vendored amd-mcp/amd_client/client.py opens its own sockets and
  drives its own login and rate limiting, so copying it into domains/
  would violate SPEC 6.2 and hand the process a second, uncoordinated
  clock. connector/client_shim.py instead provides an AMDClient-shaped
  facade — the same method surface (call(action, class_, *,
  children=None, **attrs), get_patient_bundle, get_visits_for_date,
  get_appointments_via_reminders) — implemented as pure XML request
  construction plus `await connector.sender.send()`. Copied handlers get
  one of these from their existing client factory and their call sites
  do not change. amd_mcp_common.rate_limit is correspondingly not
  copied either; connector/clock.py is the only clock in the process.
