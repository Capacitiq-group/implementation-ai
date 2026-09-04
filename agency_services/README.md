# Synkra Implementation AI Employee

Standalone repo, decoupled from `synkra-core` — reads/writes the shared
Agency PocketBase instance directly, per `ARCHITECTURE.md` (authoritative
schema reference) plus `ARCHITECTURE-ADDENDUM.md` (delivered alongside
this package — hand it to whoever maintains `ARCHITECTURE.md` so the new
collections get folded in there too).

## Current status: all 4 services built

Speed to Lead, Voice Agent, Lead Reactivation, and Custom Agentic AI
Employee all have real `implement()` + `self_test()` logic. **20 passing
tests** across six files. Nothing left stubbed at the implementer level —
what's left is wiring to real sandbox credentials (see "Running it for
real" below), not more Python to write.

## Custom Agentic AI Employee — the one structural difference

Unlike the other three, this service is bespoke per client (from your
discovery/onboarding call), so `implement()` doesn't provision
Twilio/ElevenLabs — what integrations a given instance needs depends
entirely on the client's workflow. What it does unconditionally: builds a
prompt that always encodes the `can_do_automatically` /
`requires_approval` / `never_do` split and the full
`security_requirements` list from boundaries, regardless of what's
bespoke around them — see `system_prompts.build_custom_agentic_employee_prompt`.

Because this is the most autonomous, highest-risk service, every
successful run adds a **standing** human-review flag — not conditional on
anything looking wrong, just a deliberate nudge that bespoke
decision/escalation logic always deserves a careful read before
activation.

Its self-test defines five scenarios instead of three; the two that
matter most: `approval_required_action_stops_and_asks` (feed it a
requires-approval scenario, confirm it actually stops rather than acting)
and `permission_boundary_probe` (confirm it refuses a tool outside its
granted `tool_permissions`). Both still `fail` with "not wired yet,"
consistent with the other services — same honest state, not overstated.

## What's actually here

**All four services, fully implemented:**
- `services/speed_to_lead.py` — validates intake, provisions outbound
  Twilio, flags out-of-scope lead sources (DB-driven), builds the
  qualifying-call prompt, creates the ElevenLabs agent.
- `services/voice_agent.py` — validates intake, provisions inbound
  Twilio, flags CRM/booking-integration requests, builds the
  client-facing prompt, creates the ElevenLabs agent.
- `services/lead_reactivation.py` — validates intake, enforces the
  suppression/opt-out compliance rule for real (not just described),
  blocks on an all-suppressed result, builds the personalisation prompt.
- `services/custom_agentic_employee.py` — validates discovery output,
  builds a prompt that always encodes the mandatory guardrails above,
  flags missing tool permissions rather than assuming access, standing
  human-review flag on every run.

**Supporting infrastructure:**
- `models.py` — data model matching `ARCHITECTURE.md` §3 plus
  `ServiceConfig`. Everything keyed by `agency_client_service_id`.
- `system_prompts.py` — orchestrator guardrail prompt, full
  service-boundary reference, working prompt builders for all four
  services.
- `services/base.py` — shared implement → self-test → report lifecycle.
- `orchestrator.py` / `main.py` — dispatch, status transitions, upserts
  `agency_service_configs`, never sets `active`.
- `integrations/` — `pocketbase_client.py` (incl. `list_records`),
  `twilio_client.py`, `elevenlabs_client.py`, `package_boundaries.py`
  (DB-driven package/tier rules, hardcoded fallback flagged when used),
  `suppression_list.py` (compliance-critical, always a real query).

## What I actually verified before handing this over

```
speed_to_lead:            3/3 passed
voice_agent:               4/4 passed
lead_reactivation:        7/7 passed
orchestrator:              1/1 passed
custom_agentic_employee:  5/5 passed
-----------------------------------
TOTAL:                   20/20 passed
```

Ran the full suite together in one pass (not each file in isolation) to
confirm no cross-service regressions — the `package_boundaries` retrofit
after Lead Reactivation, for instance, needed Speed to Lead's and Voice
Agent's tests re-verified, not just assumed still-passing.

`python3 -m py_compile` across every file also passes. Ran directly
(`python3 -c "..."`), not via `pytest` — this container can't reach
PyPI (confirmed — `pip install httpx` fails here). Same behaviour once
you run `pip install -r requirements.txt && pytest tests/` somewhere
with network access.

**Not tested, cannot be from here:** anything touching a real Twilio,
ElevenLabs, or PocketBase instance.

## Running it for real

1. Deploy as its own service — own repo, own host/port, decoupled from
   `synkra-core`.
2. Set the env vars from `portal-integration-brief.md` §9 — a scoped,
   non-superuser PocketBase service-account token per `ARCHITECTURE.md` §5.
3. Create the collections `ARCHITECTURE.md` §3 and
   `ARCHITECTURE-ADDENDUM.md` describe — none exist yet:
   `intake_forms`, `onboarding_notes`, `implementation_reports`,
   `agency_service_configs`, `service_packages`, `agency_suppressed_contacts`.
4. Fold the addendum into `ARCHITECTURE.md` proper.
5. Decide who writes to `agency_suppressed_contacts` on a real unsubscribe
   (open question in the addendum — likely `synkra-core`, not built yet).
6. Finish the production paths in `integrations/twilio_client.py` and
   `elevenlabs_client.py`, then re-run every service's self-test
   scenarios for real against sandbox credentials — that's the actual
   remaining proof-of-life step, not more implementer code.

## On the intake form / onboarding notes schema

Still provisional across all four services — `ARCHITECTURE.md` itself
calls `intake_forms.data` "a first draft." Keep each service's field
lookups in `system_prompts.py` and the `services/*.py` files in sync with
whatever the real forms ship with.
