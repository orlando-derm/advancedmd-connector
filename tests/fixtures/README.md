# Fixtures

Scrubbed AdvancedMD replies, one per verified tool (SPEC 9.3 step 3,
SPEC 20).

## Rules

1. **Nothing here is live data.** Every file in this directory is either
   (a) a hand-written synthetic fixture, or (b) a recording produced by
   `scripts/record_fixture.py` and scrubbed by that script's PHI
   allowlist, reviewed by the operator on the box before commit
   (SPEC 23.3 steps 2-3).
2. **Hand-written fixtures start with a provenance line**, exactly:

   ```
   synthetic fixture - hand-written from reference client XML shapes, contains no real patient data
   ```

   as an XML comment (`<!-- ... -->`) or a JSON `_provenance` key.
3. **Agents never create a fixture from live data.** An agent task that
   genuinely needs a new recording stops and asks the operator
   (SPEC 23.3 step 4). There is no exception to this.
4. **No PHI, ever** -- not a real name, dob, address, phone, ssn, chart
   number, email, memo, or note text, and not in a filename either.

## Naming

`<tool>.reply.xml` for the scrubbed reply, `<tool>.request.xml` for the
request as posted. Both are committed so the integration tests can assert
the request shape as well as the parsed result (SPEC 23.2).
