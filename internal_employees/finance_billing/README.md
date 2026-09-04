# Finance & Billing — Internal AI Employee

Targets the **Agency PocketBase instance** (same one `agency_services/`
uses) — NOT `synkra-os`'s instance. `zoho_contact_id` and the
quotation→invoice pipeline live there per `ARCHITECTURE.md`. New
collection this needed (`agency_billing_documents`) is documented in
`../agency_services/ARCHITECTURE-ADDENDUM.md` alongside the others.

## What it does

1. **`draft_quotes()`** — finds `agency_client_services` records with no
   quote yet, pulls pricing from the record itself (`setup_price`/
   `monthly_price` — the actual agreed deal for that client, locked at
   purchase time, never recomputed from `service_packages`' generic tier
   default), pulls descriptive content from `service_packages` (what's
   included, for the quote line-item description only), finds-or-creates
   the Zoho contact by email, drafts a Zoho estimate, records it in
   `agency_billing_documents` with `status: "drafted"`.
2. **`sync_document_statuses()`** — for documents a human has already
   moved to `status: "sent"` (outside this employee's control), re-checks
   Zoho's own status and reflects any change (accepted/declined/paid/
   overdue) back onto the local record.

## It never sends anything, on purpose

Every quote/invoice this employee creates in Zoho is a **draft** —
`integrations/zoho.py`'s `create_draft_estimate` never passes `send`,
which defaults to not emailing the customer. `guardrails.py`'s
`assert_never_marked_sent` is a second, independent check `worker.py`
calls before every write, specifically so a future code change can't
accidentally start marking things "sent" without that failing loudly
rather than silently. A human always takes the actual send action,
through Zoho's own UI or a separate, explicitly-approved step — not
built here, and deliberately not this employee's decision to make. Same
principle as the Custom Agentic Employee's approval-gated actions:
money-committing steps get prepared, not executed, by an AI.

## What I verified before handing this over

```
packages:   10/10 passed — line-item construction from real record data,
             using the actual agreed price not a recomputed default,
             correctly raising rather than guessing when pricing is missing
guardrails:  5/5 passed — expiry-date calculation, and the never-sent
             invariant rejecting "sent"/"paid"/etc. from the drafting path
worker:      8/8 passed — the full discover→price→contact→draft→record
             flow, blocked-document writes for every missing-data case
             (no client, no pricing), skip-if-already-quoted dedup, status
             sync updating only on real change, and unmapped Zoho statuses
             correctly returning None rather than a guessed mapping
-------------------------------------------------------------------------
TOTAL:      23/23 passed
```

`python3 -m py_compile` passes across every file, and the worker module
imports cleanly with zero network access (confirmed in this container —
also confirmed `httpx` and `pytest` aren't installable here, which is why
these tests use plain `assert`/manual `try`-`except` rather than
`pytest.raises`, consistent with every other test file in this repo).

**Not testable here:** the actual Zoho OAuth token refresh and API calls
— no live Zoho credentials, no network. The field names and endpoint
shapes (`customer_id`, `line_items` with `name`/`description`/`rate`/
`quantity`, `Zoho-oauthtoken` auth header, `organization_id` as a
required query param, the standard `grant_type=refresh_token` OAuth flow)
were confirmed against Zoho's current docs and real API-issue threads
while writing this, not assumed — but "confirmed against docs" and
"actually run against a live org" are different bars, and only the first
one has been cleared here.

## Setup

1. Add `agency_billing_documents` to the Agency PocketBase instance —
   schema in `../agency_services/ARCHITECTURE-ADDENDUM.md`.
2. Create this employee's own scoped, non-superuser PocketBase
   service-account credentials — read on `clients`, `agency_client_services`,
   `service_packages`; create+update (own records only) on
   `agency_billing_documents`. No write access needed on `clients`,
   `agency_client_services`, or `service_packages`.
3. Set up a Zoho Books API client: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`,
   a refresh token (`ZOHO_REFRESH_TOKEN`) from Zoho's OAuth consent flow,
   `ZOHO_ORGANIZATION_ID` (from Zoho Books' Manage Organizations page or
   the `GET /organizations` endpoint). Confirm which data center your
   Zoho org is on and set `ZOHO_ACCOUNTS_BASE_URL`/`ZOHO_BOOKS_BASE_URL`
   accordingly if not the default `.com` region.
4. Set `POCKETBASE_URL`/`POCKETBASE_SERVICE_TOKEN` (the Agency instance),
   `POLL_INTERVAL_SECONDS`.
5. Run a handful of real drafts against a Zoho sandbox/test organization
   first, not production — confirm the line-item formatting and pricing
   actually look right in Zoho's own UI before trusting this against real
   clients.
6. Run `python -m internal_employees.finance_billing` or wire into
   whatever process supervisor you're using.

## Deliberately not built yet (roadmap items, not gaps in this piece)

Per the roadmap this employee was scoped against: revenue reporting
(MRR, churn), infrastructure cost tracking, and Paystack payment/failed-
payment monitoring are all "Finance & Billing" responsibilities per that
roadmap but out of scope for this first build, which was specifically
the quote-from-defined-packages piece. Natural next additions to this
same package, not a different employee.
