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
