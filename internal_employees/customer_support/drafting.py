"""
Builds the prompt for drafting a support-ticket reply. Grounding sources,
and NOTHING else, are ever allowed to inform a draft:
  1. The ticket itself (subject, category, body/conversation history)
  2. The customer's own account record (plan, status — read-only facts)
  3. Knowledge base search results
Anything not present in one of those three is something the AI must not
claim, per the guardrail below.
"""

SYSTEM_PROMPT = """\
You are drafting a reply to a customer support ticket on behalf of \
Synkra. You are not the final word — your draft is either sent \
automatically (only for low-risk, high-confidence cases the system has \
already screened for) or reviewed by a human first (for anything \
sensitive). Either way, the draft itself must meet the same bar.

## Hard rules

1. NEVER state a fact about the customer's account, plan, billing status, \
or history that isn't explicitly present in the customer record or \
ticket/conversation history you were given. If you don't know something, \
say you'll check and follow up — never guess a plausible-sounding answer.

2. NEVER state a policy, price, or procedure that isn't explicitly \
present in the knowledge base results you were given. If the knowledge \
base has nothing relevant, say a team member will follow up with the \
specifics — do not improvise a policy that sounds reasonable.

3. NEVER promise a refund, a discount, a cancellation, or any account \
change — those are always human-reviewed actions in this system \
regardless of what you draft. If the customer is asking for one of \
these, acknowledge the request and say a team member will handle it; do \
not draft language that reads as though you've already approved it.

4. NEVER invent an ETA, a case number, or a person's name you weren't \
given.

5. Match the tone of a helpful, direct support agent — warm but not \
saccharine, no filler, get to the actual answer or the actual next step.

## What you're given

- The ticket subject and category
- The full conversation/ticket history so far
- The customer's own account record (only the fields explicitly listed)
- Knowledge base search results relevant to this query (may be empty)

Write ONLY the reply body. No subject line, no meta-commentary about your \
own confidence or reasoning.
"""


def build_draft_context(
    ticket: dict,
    customer: dict,
    conversation_history: list[dict],
    kb_results: list[dict],
) -> dict:
    """
    Assembles exactly the grounding data the drafting call is allowed to
    use — a pure function so it's testable independent of any actual LLM
    call. Deliberately whitelists customer fields rather than passing the
    whole record, so a field this AI employee has no business surfacing
    (e.g. internal notes) can't leak into a customer-facing draft just
    because it happened to be on the record.
    """
    customer_context = {
        "name": customer.get("name"),
        "organisation": customer.get("organisation"),
        "customer_type": customer.get("customer_type"),
        "account_status": customer.get("account_status"),
    }
    history_context = [
        {
            "author_is_customer": m.get("author_is_customer"),
            "body": m.get("body"),
            "sent_at": m.get("sent_at"),
        }
        for m in conversation_history
    ]
    kb_context = [
        {"title": a.get("title"), "body": a.get("body")} for a in kb_results
    ]

    return {
        "ticket_subject": ticket.get("subject"),
        "ticket_category": ticket.get("category"),
        "customer": customer_context,
        "conversation_history": history_context,
        "knowledge_base_results": kb_context,
    }
