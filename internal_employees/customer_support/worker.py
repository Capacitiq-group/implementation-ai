"""
Main loop for the Customer Support AI Employee worker.

Two responsibilities per cycle:
1. discover_and_submit() — find open tickets with no ai_job yet, submit
   one for each (via /api/ai-jobs/submit, using the cheap submit-time
   gate in guardrails.choose_submit_action).
2. execute_queued_jobs() — pick up this employee's own queued jobs,
   draft a reply, decide auto-send vs. self-escalate (execution-time
   gate: guardrails.should_auto_send), and report the result.

Drafting itself (the actual LLM call) is NOT wired to a real provider —
same honest "not wired yet" state as the Implementation Employee's
self-test scenarios. draft_reply() below is where that call goes; right
now it returns a clearly-marked placeholder with confidence=0.0, which
guardrails.should_auto_send will always route to self-escalation, never
an accidental auto-send of unreviewed placeholder text.
"""

import asyncio

from . import discovery, guardrails, knowledge
from .config import settings
from .drafting import build_draft_context
from .integrations.pocketbase import synkra_os


async def draft_reply(ticket: dict, customer: dict, conversation_history: list[dict], kb_results: list[dict]) -> tuple[str, float]:
    """
    Returns (draft_body, confidence). NOT WIRED to a real LLM call yet —
    see module docstring. When wired: call the LLM with drafting.SYSTEM_PROMPT
    and build_draft_context(...)'s output, parse a confidence score from
    the response (or a separate self-rating call), and return both.
    """
    context = build_draft_context(ticket, customer, conversation_history, kb_results)
    placeholder = (
        f"[NOT WIRED — no LLM call configured yet. Would draft a reply here "
        f"grounded in: ticket subject {context['ticket_subject']!r}, "
        f"{len(context['conversation_history'])} prior message(s), "
        f"{len(context['knowledge_base_results'])} knowledge base result(s).]"
    )
    return placeholder, 0.0


async def discover_and_submit() -> list[dict]:
    tickets = await discovery.find_tickets_needing_a_job()
    submitted = []
    for ticket in tickets:
        action = guardrails.choose_submit_action(
            category=ticket.get("category") or "other",
            ticket_subject=ticket.get("subject", ""),
        )
        guardrails.assert_action_is_safe(action)
        result = await synkra_os.submit_ai_job(
            task=f"Investigate and draft a reply to ticket {ticket.get('ticket_number', ticket['id'])}",
            action=action,
            input_reference=ticket["id"],
        )
        submitted.append({"ticket_id": ticket["id"], **result})
    return submitted


async def execute_job(job: dict) -> None:
    ticket_id = job.get("input_reference")
    if not ticket_id:
        await synkra_os.report_job_result(
            job["id"], status="failed", error="No input_reference (ticket id) on this job."
        )
        return

    try:
        ticket = await synkra_os.get_record("support_tickets", ticket_id)
    except Exception as exc:
        await synkra_os.report_job_result(job["id"], status="failed", error=f"Could not load ticket: {exc}")
        return

    customer = await synkra_os.get_record("customers", ticket["customer"]) if ticket.get("customer") else {}
    conversation_history = await synkra_os.list_records(
        "conversations", filter_expr=f"ticket = '{ticket_id}'", sort="+sent_at"
    )
    kb_results = await knowledge.search_knowledge_base(f"{ticket.get('subject', '')} {ticket.get('category', '')}")

    draft_body, confidence = await draft_reply(ticket, customer, conversation_history, kb_results)

    # Note: ai_jobs doesn't persist the `action` a job was submitted
    # under onto the job record itself — ai_jobs.pb.js only uses it
    # transiently at submit time to compute human_review_required. So
    # execution can't look up "what action was this submitted under,"
    # and doesn't need to: a job the server already flagged
    # human_review_required=true stays gated no matter what status this
    # worker reports (see ai_jobs.pb.js's /result handler). This only
    # needs to get the auto-send decision right for jobs the server left
    # open — which is exactly what should_auto_send(confidence) does.
    result_payload = {
        "ticket_id": ticket_id,
        "draft_reply": draft_body,
        "confidence": confidence,
        "knowledge_base_articles_used": [a.get("id") for a in kb_results],
    }

    if guardrails.should_auto_send(confidence):
        send_result = await synkra_os.send_email(
            to=customer.get("email", ""),
            subject=f"Re: {ticket.get('subject', 'Your support request')}",
            html=draft_body,
            related_customer_id=customer.get("id", ""),
        )
        result_payload["sent"] = True
        result_payload["email_event_id"] = send_result.get("email_event_id")
        await synkra_os.create_record("conversations", {
            "ticket": ticket_id,
            "customer": customer.get("id", ""),
            "channel": "email",
            "author_is_customer": False,
            "body": draft_body,
            "sent_at": _now_iso(),
        })
        await synkra_os.report_job_result(job["id"], status="succeeded", result=result_payload)
    else:
        result_payload["sent"] = False
        result_payload["reason"] = "Confidence below auto-send threshold — self-escalated for human review."
        await synkra_os.report_job_result(job["id"], status="escalated", result=result_payload)


async def execute_queued_jobs() -> int:
    jobs = await synkra_os.list_records(
        "ai_jobs",
        filter_expr=f"ai_employee = '{settings.ai_employee_id}' && status = 'queued'",
        sort="+created",
    )
    for job in jobs:
        await execute_job(job)
    return len(jobs)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def run_once() -> None:
    await discover_and_submit()
    await execute_queued_jobs()


async def run_forever() -> None:
    while True:
        await run_once()
        await asyncio.sleep(settings.poll_interval_seconds)
