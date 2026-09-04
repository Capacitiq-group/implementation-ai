# implementation-ai

> **Architecture:** the canonical description of Synkra's PocketBase instances,
> which repo uses which one, and the identity model lives in one place:
> [`SYNKRA-ARCHITECTURE.md` in `synkra-os`](https://github.com/Capacitiq-group/synkra-os/blob/main/SYNKRA-ARCHITECTURE.md).
> Do not restate it here — update it there.


Two Python packages sharing this repo, per Capacitiq's own call: they do
different jobs but are the same kind of system — an AI that does real
work against a PocketBase instance, drafts/decides within explicit
guardrails, and defers to a human for anything above its authorised risk
level. Same testing discipline (mocked-network tests, pure functions for
anything that's actually a guarantee, honest "not wired yet" states
instead of faked integrations) applies to both.

## `agency_services/`

The Implementation AI — builds/configures the AI services an **Agency
client** has purchased (Voice Agent, Speed to Lead, Lead Reactivation,
Custom Agentic AI Employee), against the dedicated Agency PocketBase
instance. Implements, self-tests, writes a report. Never activates a
service itself — a human always does final QC.

20 tests. See `agency_services/README.md` for full detail, including the
one open architectural question it surfaced (where live per-service
config persists, given this agent's deliberately narrow write access)
and `agency_services/ARCHITECTURE-ADDENDUM.md` for the three PocketBase
collections it needed that didn't exist before this was built.

## `internal_employees/`

Synkra's own internal AI Employees — different job function, same
pattern. Built so far:

- **`customer_support/`** (27 tests): discovers open support tickets in
  `synkra-os`, drafts replies via Ollama grounded only in known account
  facts, auto-sends the low-risk/high-confidence cases, escalates
  everything else. See its README for the two-gate risk model
  (submit-time category screen + execution-time confidence threshold)
  and the gaps it surfaced in `synkra-os` itself.
- **`finance_billing/`** (23 tests): targets the Agency PocketBase
  instance (not `synkra-os`) — drafts Zoho Books quotes from a client's
  actual purchased-service pricing and the `service_packages` catalog,
  never auto-sends anything (drafts only — a human always sends), syncs
  document status back from Zoho once a human has sent one. See its
  README for why pricing always comes from the record itself, never a
  recomputed default.

Future internal AI Employee roles (sales, technical ops, admin, etc.) go
here as siblings of the above, per the roadmap in this project's own
notes.

## Running tests

Each package's tests are independent — no cross-package dependencies.
From the repo root:

```
pip install -r agency_services/requirements.txt
pip install -r internal_employees/customer_support/requirements.txt
pip install -r internal_employees/finance_billing/requirements.txt
python -m pytest agency_services/tests/ internal_employees/customer_support/tests/ internal_employees/finance_billing/tests/
```


38 tests total, all passing as of this repo's assembly — verified by
running every test function directly (not just compiling) after the
move into this shared-repo layout, since a few tests use hardcoded
module-path strings for mocking (`unittest.mock.patch("some.module.path")`)
that don't survive a package rename automatically — one such case was
caught and fixed in `agency_services/tests/test_lead_reactivation.py`
during this assembly. Worth remembering if either package gets
restructured again later: `patch()`-by-string-path is exactly the kind
of thing a rename silently breaks without a test run catching it.
