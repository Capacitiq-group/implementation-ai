# Customer Support AI Employee — Python Worker

The Python worker `ai_jobs.pb.js` in `synkra-os` describes but doesn't
implement ("This is the connection point for a future Python AI worker
project"). This is that project, for the `customer_support` function.

## What it actually does right now

1. **Discovers work**: finds `support_tickets` with `status = 'open'`
   that don't have an `ai_jobs` record yet (dedup via `input_reference`
   — see the note in `discovery.py` about why not `related_ticket`),
   submits a job for each via the real `/api/ai-jobs/submit` route.
2. **Gates risk at submit time**: `guardrails.choose_submit_action`
   tags each job `"support.manage"` (billing/account categories, or any
   sensitive keyword — cancel, refund, complaint, legal, etc.) or
   `"email.manage"` (everything else) — mirroring `ai_jobs.pb.js`'s own
   `ALWAYS_REQUIRES_REVIEW` set exactly, so the server's human-review
   gate fires correctly regardless of what this worker decides later.
3. **Executes queued jobs**: loads the ticket, customer record, full
   conversation history, and a knowledge-base search — real PocketBase
   reads, all through this employee's own scoped login (see
   `bootstrap_ai_customer_support_employee.sh`), never a superuser.
4. **Gates risk again at execution time**: even for a job tagged
   `"email.manage"` (not forced to review), `guardrails.should_auto_send`
   requires ≥0.85 confidence before actually sending. Below that, it
   self-escalates — reports `status: "escalated"` instead of `"succeeded"`,
   which the server accepts regardless of the original action tag.
5. **Logs what it sends**: every auto-sent reply gets written to
   `conversations` (a permission this employee actually holds —
   `support.view` is enough to create one, per the migration).

## What's NOT wired — and why that's currently the safe state, not a bug

`draft_reply()` in `worker.py` doesn't call a real LLM yet — it returns
a clearly-marked placeholder with **confidence 0.0**. Combined with the
0.85 auto-send threshold, this means **every single job self-escalates
right now**, unconditionally. `test_execute_job_self_escalates_when_drafting_is_not_wired`
proves exactly this — the one property that matters most while drafting
is unwired: it never auto-sends a placeholder to a real customer.
`test_execute_job_auto_sends_when_confidence_clears_threshold` separately
proves the auto-send path itself is correct, using a mocked high-confidence
draft — so both "doesn't fire today" and "will work correctly once wired"
are independently verified, not just assumed.

## Three real gaps this surfaced in synkra-os itself (not mine to fix silently)

1. **No incoming-email ingestion.** `email_adapter.pb.js` only sends and
   tracks delivery/bounce/complaint status — there's no route or worker
   that turns a customer's *incoming* email into a ticket or conversation.
   Right now this worker's only real trigger source is `support_tickets`
   created through the existing UI. Email and the planned chat widget
   aren't real input channels yet — they need their own ingestion
   pipelines before "omnichannel" is actually true, not just configured.
2. **`ai_jobs.related_ticket` is unused by the real submit route.** The
   schema has it; `/api/ai-jobs/submit` never sets it, only the generic
   `input_reference` text field. Discovery here works around that
   correctly (see `discovery.py`), but if `related_ticket` gets wired up
   later, switch dedup to use it — it's the more correct field.
3. **What happens after a human approves an escalated job is genuinely
   unresolved in synkra-os**, not just here. `/api/ai-jobs/:id/review`'s
   own comment says approval "does not itself execute anything: any
   actual mutation ... still has to go through that module's own
   permissioned, audited route." This worker's employee role deliberately
   does **not** hold `support.manage` (see `guardrails.py`'s module
   docstring for why granting it would let this worker bypass the review
   gate entirely). So today, a human approving an escalated
   `"support.manage"`-tagged job still has to go perform the actual
   ticket update themselves through the normal Support UI, using the
   job's `result` (the draft) as their reference — approval records the
   *decision*, not the *action*. That's a defensible design, but it's a
   real workflow gap worth knowing about, not something this worker
   quietly papers over.

## What I verified before handing this over

```
guardrails: 9/9 passed — including an exhaustive check that
             choose_submit_action can NEVER return a denylisted or
             unpermitted action across every category/keyword combination
knowledge:  5/5 passed — filter-builder correctness, including quote
             escaping and short-word filtering
worker:     4/4 passed — discovery dedup, submit-time action selection,
             the self-escalation guarantee while drafting is unwired,
             and the auto-send path working correctly once it is
-------------------------------------------------------------------
TOTAL:     18/18 passed
```

`python3 -m py_compile` across every file passes, and the worker module
imports cleanly with zero network access (confirmed in this container).
Ran directly (`python3 -c "..."`), not via `pytest` — no PyPI access
here.

## Setup

1. Apply `pocketbase/pb_migrations/1735500018_knowledge_base.js` to
   `synkra-os` (adds `knowledge_base_articles` + the `knowledge.view`/
   `knowledge.manage` permissions).
2. Run `scripts/bootstrap.sh` first (if not already done), then
   `scripts/bootstrap_ai_customer_support_employee.sh` — creates the
   `AI — Customer Support` role, its employee record, its login, and the
   `ai_employees` record. Note the printed `ai_employees` id.
3. Set `AI_WORKER_API_KEY` in synkra-os's own env (separate secret, only
   for `/api/ai-jobs/:id/result`).
4. Set this worker's env: `SYNKRA_OS_BASE_URL`, `AI_EMPLOYEE_LOGIN_EMAIL`/
   `PASSWORD` (from step 2), `AI_EMPLOYEE_ID` (the printed id),
   `AI_WORKER_API_KEY` (same value as step 3), `POLL_INTERVAL_SECONDS`.
5. Populate `knowledge_base_articles` with real content — retrieval only
   works once there's something to retrieve.
6. Wire `draft_reply()` to a real LLM call, using `drafting.SYSTEM_PROMPT`
   and `build_draft_context()`'s output — and have it actually return a
   real confidence score, not a hardcoded value.
7. Run `python worker.py` (add a small `__main__` entry calling
   `asyncio.run(run_forever())`) or wire it into whatever process
   supervisor you're using.
