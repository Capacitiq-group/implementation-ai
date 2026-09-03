"""
Finds open support tickets that don't have an ai_job yet, so the worker
can queue itself work rather than waiting for a human to manually
trigger every ticket via /api/ai-jobs/submit.

Deliberately does NOT write anything to support_tickets to mark "AI has
seen this" (e.g. ai_involved) — that field's collection requires
support.manage to update, which this employee's role doesn't hold (see
guardrails.py's module docstring for why: granting it directly would let
this worker bypass the ai_jobs human-review gate entirely by just
PATCHing a ticket's status itself, defeating the point).

Dedup note (flagging a real mismatch, not silently working around it):
ai_jobs has a `related_ticket` relation field, which looks like the
obvious dedup key — but ai_jobs.pb.js's actual /api/ai-jobs/submit route
never sets it; it only ever sets the generic text field
`input_reference` (per that route's code and the schema comment: "kept
generic rather than a hard relation"). So dedup here uses
`input_reference == ticket.id` instead, since that's what the real route
actually populates. If `related_ticket` gets wired up in a future
synkra-os change, switch this to use it instead — it's the more correct
field for this purpose.
"""

from .integrations.pocketbase import synkra_os


async def find_tickets_needing_a_job() -> list[dict]:
    open_tickets = await synkra_os.list_records(
        "support_tickets", filter_expr="status = 'open'", sort="+opened_at"
    )
    if not open_tickets:
        return []

    existing_jobs = await synkra_os.list_records(
        "ai_jobs", filter_expr="input_reference != ''", per_page=500
    )
    ticket_ids_with_jobs = {j.get("input_reference") for j in existing_jobs}

    return [t for t in open_tickets if t["id"] not in ticket_ids_with_jobs]
