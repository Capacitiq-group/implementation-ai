# Integration Brief — Admin Panel, Client Portal & Implementation AI Employee

**Note: `ARCHITECTURE.md` (delivered separately) is now the authoritative
schema reference and supersedes this doc's collection names and keying.**
The correction that matters most: onboarding/implementation state lives
on `agency_client_services.onboarding_status`, keyed by
`agency_client_service_id` — **not** on a `clients.status` field keyed by
`client_id`, as this doc originally said. A client can have multiple
purchased services, each independently mid-onboarding. Everywhere below
that still says `client_id` for onboarding/implementation purposes should
be read as `agency_client_service_id`; §10's collection list is superseded
by `ARCHITECTURE.md` §3's fuller version. The screens, endpoint shapes,
and env-var reasoning below are still accurate — just re-key them.

For whoever's building the admin panel and client portal. This covers what
those two systems need to share with the Implementation AI Employee
(separate build, see the accompanying spec doc) so all three work off the
same source of truth from day one.

## 1. Recommended approach: one shared PocketBase instance, three separate deployed apps

Synkra already uses PocketBase as the backend across every service
(`clients`, `leads`, `campaign_leads` collections, PocketBase auth for
access control). The simplest integration — and the one I'd recommend
rather than building separate REST bridges between three systems — is:
**all three apps read and write the same (new, Agency-dedicated —
see §11) PocketBase instance**, with permission rules scoping who can
see/change what.

Per your call, these are three separately deployed things, not one
codebase:
- **Admin panel** — its own repo/deploy.
- **Client portal** — its own repo/deploy.
- **Implementation AI Employee** — its own repo/deploy, decoupled from
  `synkra-core` entirely. It doesn't import `synkra-core`'s internal
  Twilio/ElevenLabs/PocketBase helper functions (there's no code
  dependency between the two repos) — it has its own thin wrappers
  around those same SDKs. The only thing it shares with `synkra-core` is
  the *data* — the Agency PocketBase instance — not code.

PocketBase is still what avoids needing a sync layer between the three —
they coordinate through shared collections and the `status` state
machine (§2), not through calling each other's internal code.

## 2. Client status — one state machine, shared by all three apps

Every client record needs a single `status` field all three systems read
and (in the right places) write:

```
quotation_sent
  → invoiced
  → paid                      (client portal: grants login access)
  → intake_form_completed     (client portal: client fills form)
  → onboarding_scheduled      (admin panel)
  → onboarding_completed      (admin panel)
  → onboarding_notes_ready    (admin panel: you finalize notes, add
                                any extra info)
  → implementation_triggered  (admin panel: you manually fire it)
  → implementing              (Implementation Employee: in progress)
  → pending_qc                (Implementation Employee: done, report
                                ready, waiting on you)
  → active                    (admin panel: you approve)
  → paused / cancelled        (either, as needed later)
```

Each status transition should be logged (who/what changed it, when) —
useful both for your admin visibility and for debugging if the
Implementation Employee gets triggered on an incomplete record.

## 3. Data the Implementation Employee needs to read

It needs two things bundled together, not the form alone (per your
process): the **intake form** and your **onboarding notes**. Minimum
proposed schema — refine once the actual intake form is built:

**`intake_forms` collection**
- `client_id` (relation)
- `service` (which of Voice Agent / Speed to Lead / Lead Reactivation /
  Custom Agentic AI Employee)
- `plan_tier`
- Service-specific fields (e.g. for Voice Agent: business description,
  services + prices, hours, FAQs, transfer rules — the same inputs the
  system-prompt template in `08-agency-services.md` already expects)
- `submitted_at`

**`onboarding_notes` collection**
- `client_id` (relation)
- `call_held_at`
- `notes` (free text or structured — your call)
- `changes_from_form` (what changed/was added vs. the intake form)
- `additional_info` (anything you add after the call, before triggering)
- `finalized_by`, `finalized_at`

The Implementation Employee treats `intake_forms` + `onboarding_notes`
together as its input when it starts the implement stage.

## 4. Data the Implementation Employee writes back

**`implementation_reports` collection** (new)
- `client_id`, `service`
- `status` (`in_progress` / `ready_for_qc` / `needs_review` / `blocked`)
- `steps_completed` (what it actually provisioned/configured)
- `test_results` (structured, per the shape in the spec doc §4)
- `flags_for_human` (anything it couldn't determine or needs a judgment
  call on)
- `started_at`, `completed_at`

The admin panel needs a view onto this collection — this is what you QC
against before flipping a client to `active`.

## 5. Login / auth requirements

- **Client portal login:** client-scoped auth (email/password or magic
  link via PocketBase auth) — a client can only see their own record,
  their own intake form, and (once you're ready to expose it) their own
  service status/usage. No visibility into other clients or internal
  fields (system prompts, credit costs, internal notes).
- **Admin panel login:** staff-scoped auth — full visibility across all
  clients, all services, onboarding notes, implementation reports, and
  the ability to trigger implementation and approve/activate.
- **Implementation Employee access:** a service account / API key, not a  human login — needs read access to `intake_forms` + `onboarding_notes`
  for records with `status: implementation_triggered`, and write access
  to `implementation_reports` and to advance `status` between
  `implementing` and `pending_qc`. It should never have write access to
  `status: active` — that transition is admin-only, always.

## 6. Admin panel frontend — scoped to the Implementation AI Employee only

This is not the whole admin panel spec — just the screens/components this
specific piece needs. Everything else about the admin panel (billing
views, general client list, etc.) is out of scope here.

**Screen: Client detail → "Implementation" tab**

| Component | What it does | Calls |
|---|---|---|
| Onboarding notes editor | Text/structured fields per §3's `onboarding_notes` schema; a "Finalize notes" button that saves and advances `status` to `onboarding_notes_ready` | `PATCH /pb/collections/onboarding_notes/records/:id` (direct PocketBase write) |
| "Trigger Implementation" button | Enabled only when `status == onboarding_notes_ready`. Disabled with a tooltip otherwise ("Finalize onboarding notes first") | `POST /implementation/trigger` |
| Implementation status indicator | Shows current stage: not started / implementing / pending_qc / blocked. Poll or subscribe to the client record's `status` field | `GET /pb/collections/clients/records/:id` (poll every few seconds while `status == implementing`, or use PocketBase's realtime subscription instead of polling — it already supports this) |
| Implementation report viewer | Renders `steps_completed`, `test_results` (pass/fail per scenario with detail text), and `flags_for_human` prominently — flags should be the most visually prominent part, since that's what you're actually reviewing | `GET /implementation/reports/:client_id` |
| "Approve & Activate" button | Enabled only when report status is `ready_for_qc` or you've reviewed a `needs_review` report and are satisfied. Sets `status: active` | `PATCH /pb/collections/clients/records/:id` (direct write — this is an admin-only action, not something the Implementation Employee's own API should expose, per §5) |
| "Re-run implementation" button | For when a report is `blocked` or `needs_review` and you've fixed the underlying issue (e.g. added a missing intake field) — re-fires the same trigger | `POST /implementation/trigger` |

## 7. Client portal frontend — scoped to the Implementation AI Employee only

**Screen: Intake form** (the client's only direct touchpoint with this
system in v1)

| Component | What it does | Calls |
|---|---|---|
| Intake form | Gated on `status: paid` or later. Fields depend on which service the client bought — form should branch per `service` on the client record | `POST /intake/submit` |
| Submission confirmation | On success, advances `status` to `intake_form_completed` and tells the client what happens next (onboarding call gets scheduled) | handled server-side by `/intake/submit`, no separate call needed |

Not in v1, per the earlier brief: a client-facing status/progress view.
Add that later if you want clients to see "your Speed to Lead setup is in
progress" — it would just be a read of the client's `status` field,
nothing new needed from the Implementation Employee side.

## 8. Endpoint contract

These are the only endpoints the Implementation Employee itself needs to
expose — everything else above is a direct PocketBase read/write, which
both panels can already do if they're using the PocketBase SDK. Since
this is now its own deployed service (§1), the admin panel calls it at
its own base URL — see `IMPLEMENTATION_EMPLOYEE_BASE_URL` in §9 — not as
a route within `synkra-core` or either panel's own backend.

| Endpoint | Method | Called by | Body / params | Returns |
|---|---|---|---|---|
| `/implementation/trigger` | POST | Admin panel | `{"client_id": "..."}` | `{"status": "implementing"}` or an error if `status != onboarding_notes_ready` |
| `/implementation/reports/{client_id}` | GET | Admin panel | — | Latest `implementation_reports` record for that client (steps, test results, flags, overall status) |

That's genuinely it — two endpoints. Everything else (onboarding notes,
intake form, client status, activation) is a direct PocketBase collection
read/write with permission rules doing the access control, not a custom
API layer. Adding endpoints beyond these two for things PocketBase
already does directly would just be duplicate surface area to maintain.

`/implementation/trigger` should be async — return immediately with
`"status": "implementing"` and let the actual implement → self-test →
report cycle run in the background (per `orchestrator.run_implementation`
in the code), rather than holding the HTTP connection open for however
long implementation takes.

## 9. Environment variables

**For the Implementation Employee's own repo/deploy** (now standalone,
not inside `synkra-core` — §1):

| Variable | Used for | Notes |
|---|---|---|
| `POCKETBASE_URL` | Base URL of the Agency PocketBase instance (§11) | Sandbox and production should point at different instances per the earlier sandbox-setup guidance |
| `POCKETBASE_SERVICE_TOKEN` | Auth for the Implementation Employee's own reads/writes | Scoped per §5 — read `intake_forms`/`onboarding_notes`, write `implementation_reports` and the `implementing`/`pending_qc` status transitions only, never `active` |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Provisioning phone numbers, placing calls | Use separate sandbox vs. production values — never the same credential in both environments |
| `ELEVENLABS_API_KEY` | Creating/configuring conversational agents | Same sandbox/production split |
| `DEEPGRAM_API_KEY` | Call transcription | — |
| `RESEND_API_KEY` | Notification emails | — |
| `KIMI_API_KEY` | AI personalisation (Lead Reactivation) and any AI generation the Custom Agentic Employee needs | — |
| `ENVIRONMENT` | `sandbox` or `production` | Every provider call should check this before firing — this is the safety switch that stops a sandbox test from ever touching a real client's number or contact list |
| `ADMIN_PANEL_INTERNAL_API_KEY` | Verifies incoming calls to `/implementation/trigger` and `/implementation/reports/{client_id}` actually came from the admin panel | Service-to-service key, separate from any client- or staff-facing login token |

**For the admin panel's repo/deploy** (new — needed now that this is a
separate service, not a `synkra-core` route):

| Variable | Used for | Notes |
|---|---|---|
| `IMPLEMENTATION_EMPLOYEE_BASE_URL` | Where the admin panel sends `/implementation/trigger` and `/implementation/reports/{client_id}` calls | Points at wherever the Implementation Employee is deployed — a different host/port from `synkra-core` |
| `IMPLEMENTATION_EMPLOYEE_API_KEY` | The value the admin panel sends so the Implementation Employee can verify the request (matches `ADMIN_PANEL_INTERNAL_API_KEY` above) | Keep this and its counterpart in sync across both deploys' secrets |

None of these should ever be committed to the repo or pasted into chat —
standard `.env` file (gitignored) locally, and your host's secrets
manager (or Twilio/PocketBase's own env-var injection if deploying on a
platform that supports it) in sandbox/production.

## 10. PocketBase collections — what this AI reads and writes

**Reads only:**

| Collection | Fields it needs | New or existing |
|---|---|---|
| `intake_forms` | `client_id`, `service`, `plan_tier`, `data` | New (§3) |
| `onboarding_notes` | `client_id`, `notes`, `changes_from_form`, `additional_info`, `finalized_at` | New (§3) |

**Reads and writes:**

| Collection | What it reads / what it writes | New or existing |
|---|---|---|
| `clients` | Reads `status`, `service`, `plan_tier` to know whether it's allowed to run. Writes `status` transitions (`onboarding_notes_ready → implementing → pending_qc`, or back to `onboarding_notes_ready` if blocked), plus the service-specific config fields it sets during implement (`twilio_number`, `elevenlabs_agent_id`, `system_prompt`, `chroma_namespace`, etc. — same fields `08-agency-services.md` already documents). Never writes `status: active` — that stays admin-only per §5 | Existing |

**Writes only:**

| Collection | What gets written | New or existing |
|---|---|---|
| `implementation_reports` | One record per implementation run — `steps_completed`, `test_results`, `flags_for_human`, `status` (§4) | New (§4) |
| `leads` | Only during self-test, and only synthetic records — must be written with an `is_test: true` flag so they're never mistaken for a real lead in your reporting/dashboards | Existing (Speed to Lead) |
| `campaign_leads` | During Lead Reactivation's implement stage — initial campaign record + validated contact list. Real sends are the operate phase, not implementation | Existing (Lead Reactivation) |

Everything else in the existing `clients` collection (billing fields,
`banking_details`, credit balances) is out of scope for this AI — it has
no reason to read or write those, and its service account (§5,
`POCKETBASE_SERVICE_TOKEN`) shouldn't be granted access to them.

## 11. Instance architecture — a separate instance from Flow

Yes, worth doing. Recommendation: **one new PocketBase instance
dedicated to Agency** — shared by the admin panel, client portal, and
this Implementation Employee — kept separate from whichever instance
`synkra-core` already uses for Flow users.

Why this is the right split, not just "more infrastructure":
- **Different products, different data.** Flow's collections and access
  patterns have nothing to do with Agency's `clients`/`intake_forms`/
  `implementation_reports`. Mixing them into one instance means every
  permission rule has to account for both, which is exactly the kind of
  thing that causes an accidental cross-product data leak later.
- **Cleaner auth boundaries.** The client portal's login only needs to
  scope against Agency data. If it shared an instance with Flow, a
  misconfigured permission rule could expose Flow user data to an
  Agency client login, or vice versa — a real, avoidable risk, not a
  theoretical one.
- **Matches precedent, not a departure from it.** `synkra-core` already
  treats Flow's instance as separate — this isn't introducing a new
  pattern, it's applying the one you already have to a second product.
- **Independent scaling/backup.** Agency's onboarding-heavy write
  pattern (intake forms, onboarding notes, implementation runs) and
  Flow's usage pattern can scale and back up independently once
  they're not sharing one instance's resources.

One instance, three consumers (admin panel, client portal, Implementation
Employee) — same as §1's original recommendation, just now explicitly
scoped as its own instance rather than assumed to be whatever instance
already exists. `POCKETBASE_URL` (§9) should point at this new instance,
not Flow's.

