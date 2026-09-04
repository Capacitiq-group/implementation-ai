# ARCHITECTURE.md Addendum — service_packages, agency_suppressed_contacts, agency_service_configs & agency_billing_documents

Proposed new collection, same format as §3 of `ARCHITECTURE.md`. Reason:
per that doc's CRUD table, the AI Implementation Agent can write
`agency_client_services` for `onboarding_status` only, and has no write
access to `clients` at all — so the actual config it produces (Twilio
number, ElevenLabs agent id, generated system prompt, etc.) had nowhere
to live that `synkra-core`'s runtime side could read it from. This
collection is that place.

### `agency_service_configs`
Current live config for a service, as produced by the AI Implementation
Agent. One record per `agency_client_service_id`, upserted on every
(re-)implementation — this is "current config," distinct from
`implementation_reports`, which stays a per-run audit log (multiple
reports can exist over time; this collection never accumulates history,
it's overwritten).

**Fields:** `agency_client_service_id` (relation), `client_id`
(relation, denormalized for convenient scoping), `service`, `config`
(json — shape is service-specific: for Speed to Lead currently
`twilio_number`, `twilio_number_sid`, `lead_sources`,
`elevenlabs_agent_id`, `system_prompt`), `updated_at`.

| | Client Portal | Admin Panel | AI Implementation Agent | `synkra-core` |
|---|---|---|---|---|
| Create | No | No | Yes (only creator, via upsert) | No |
| Read | No | Yes (useful for QC alongside `implementation_reports`) | Own records | Yes — this is what it reads at runtime to actually run the live service |
| Update | No | No (if a correction is needed, re-trigger implementation rather than hand-editing) | Yes (upsert overwrites on re-implementation) | No |
| Delete | No | Yes (e.g. if a service is cancelled and its config should be cleared) | No | No |

Same non-superuser scoped-credential requirement as the rest of the AI
Implementation Agent's access, per `ARCHITECTURE.md` §5.

---

### `service_packages`
What a given service/tier actually includes — the admin-editable
replacement for what was previously a hardcoded transcription of
`AGENCY-SERVICES-DOCUMENTATION.md` in the AI Implementation Agent's code.
Editing a record here changes what the agent enforces without a code
deploy. When no matching record exists, the agent falls back to its
hardcoded copy and flags that in its report — so an unpopulated record
degrades gracefully rather than blocking implementation, but doesn't go
unnoticed either.

**Fields:** `service`, `tier`, `boundaries` (json — shape mirrors the
Python `SERVICE_BOUNDARIES` dict: `included_every_tier`, `never_included`,
plus service-specific structured fields the agent actually branches on,
e.g. `allowed_lead_sources` for Speed to Lead, `allowed_channels` and
`suppression_required` for Lead Reactivation), `updated_at`,
`updated_by`.

| | Client Portal | Admin Panel | AI Implementation Agent |
|---|---|---|---|
| Create | No | Yes | No |
| Read | No | Yes | Yes — reads own service/tier at implement time |
| Update | No | Yes | No |
| Delete | No | Yes | No |

Note: per `integrations/package_boundaries.py`, this is only queried in
`production` — in `sandbox`, the agent always uses the hardcoded fallback
(this data is genuinely optional, unlike the next collection).

### `agency_suppressed_contacts`
The opt-out/suppression list Lead Reactivation checks before every
campaign — the compliance guarantee that a contact who unsubscribed
never re-enters a campaign, even if the same list is re-uploaded. Unlike
`service_packages`, this is **always** queried for real, in every
environment — it's compliance-critical, not a nice-to-have fallback
scenario.

**Fields:** `client_id` (relation), `contact_email`, `suppressed_at`,
`reason` (e.g. `unsubscribed`, `bounced`, `manual`), `source` (which
system recorded the suppression — likely the email-sending
provider's webhook, or a manual Admin Panel entry).

| | Client Portal | Admin Panel | AI Implementation Agent | `synkra-core` |
|---|---|---|---|---|
| Create | No | Yes (manual entry) | No | Yes (likely creator — from unsubscribe-link/bounce webhooks) |
| Read | No | Yes | Yes — own-client-scoped, checked before every campaign | As needed |
| Update | No | No | No | No |
| Delete | No | Yes | No | No |

Open question, not resolved here: which system actually owns writing to
this collection when a real unsubscribe happens — most likely
`synkra-core`, in whatever code path handles email-provider webhooks, but
that's not built yet either. Flagging it the same way the rest of this
doc flags open gaps.

---

### `agency_billing_documents`
New collection for the Finance & Billing internal employee
(`internal_employees/finance_billing`) — one record per quote or invoice
drafted for a client's purchased service. Distinct from
`implementation_reports`/`agency_service_configs`'s pattern in one way:
this employee never writes a "sent"/"accepted"/"paid" status itself on
the drafting pass — see its README for why (money-committing actions get
the same draft-then-human-sends treatment as everywhere else in this
codebase that touches something consequential). A status-sync pass does
update status based on Zoho's own state, but only after a human has
already moved a document to `sent` outside this employee's control.

**Fields:** `agency_client_service_id` (relation), `client_id`
(relation), `document_type` (`quote`|`invoice`), `zoho_estimate_id`
(nullable), `zoho_invoice_id` (nullable), `status`
(`drafted`|`blocked`|`sent`|`accepted`|`declined`|`paid`|`overdue`),
`amount_total`, `currency`, `line_items` (json snapshot of what was
quoted — kept even if `service_packages`/pricing changes later, so a
historical quote's actual content is never ambiguous), `flags_for_human`
(json), `created_at`, `updated_at`.

| | Client Portal | Admin Panel | Finance & Billing Employee |
|---|---|---|---|
| Create | No | No | Yes (only creator — drafting pass) |
| Read | Not yet (per `ARCHITECTURE.md` §3's same "not in v1" treatment as `implementation_reports`) | Yes | Own records |
| Update | No | Yes (marking `sent` after actually sending via Zoho, manual status overrides) | Yes (status-sync pass only — reads Zoho's own state and reflects it, never sets `sent`/`accepted`/`paid` on its own initiative) |
| Delete | No | Yes | No |

**Also needed:** this employee needs read access to `clients`
(`contact_email`, `contact_name`), `agency_client_services` (pricing
fields, `service_slug`, `tier`), and `service_packages` (descriptive
content only, per `packages.py`'s deliberate separation of pricing
source-of-truth from description source-of-truth) — no write access to
any of those three. It does **not** need write access to
`clients.zoho_contact_id`; contact lookup is by email search against
Zoho itself on every run rather than caching the mapping in PocketBase,
specifically to avoid needing a new write grant on a collection this
employee has no other business touching.
