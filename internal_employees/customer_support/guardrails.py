"""
Guardrails for the Customer Support AI Employee.

IMPORTANT: the server (ai_jobs.pb.js) is the actual authority on what's
allowed — AI_GLOBAL_DENYLIST and ALWAYS_REQUIRES_REVIEW there are
enforced regardless of what this file says. The copies below are a
mirror, kept for two reasons: (1) so the worker can make a sane
action-selection decision *before* submitting a job, rather than
submitting blind and finding out the hard way, and (2) so a test can
prove this worker never even tries to select a denylisted action. If the
server's lists ever change, these must be updated to match — they are
not a second source of truth, they are advisory and must never diverge
from ai_jobs.pb.js in synkra-os.
"""

# Mirrors ai_jobs.pb.js AI_GLOBAL_DENYLIST exactly.
AI_GLOBAL_DENYLIST = {
    "billing.refund",
    "billing.modify",
    "customers.impersonate",
    "employees.manage",
    "permissions.manage",
    "infrastructure.restart",
    "deployments.execute",
    "ai.configure",
}

# Mirrors ai_jobs.pb.js ALWAYS_REQUIRES_REVIEW exactly.
ALWAYS_REQUIRES_REVIEW = {
    "customers.edit",
    "support.manage",
}

# The only two actions this specific AI employee is configured with in
# its ai_employees.permitted_actions field (see bootstrap script). Kept
# here too so choose_action() can never select something this employee
# wasn't actually granted, even if a bug elsewhere tried to.
PERMITTED_ACTIONS = {"email.manage", "support.manage"}

# Ticket categories/situations that should never be auto-sent regardless
# of how confident the draft looks — these are exactly the cases where a
# plausible-sounding wrong answer does the most damage.
ALWAYS_ESCALATE_CATEGORIES = {"billing", "account"}
ALWAYS_ESCALATE_KEYWORDS = {
    "cancel", "cancellation", "refund", "chargeback", "lawsuit", "legal",
    "complaint", "angry", "unacceptable", "scam", "fraud",
}

MIN_CONFIDENCE_FOR_AUTO_SEND = 0.85


def choose_submit_action(category: str, ticket_subject: str, ticket_body: str = "") -> str:
    """
    Pure function, used at SUBMIT time — before any reply has been
    drafted, so no confidence score exists yet. Decides only from
    cheap, known-upfront signals: category and keywords. Returns
    "support.manage" (always reviewed) for anything sensitive, or
    "email.manage" (a *candidate* for auto-send, not a guarantee — see
    should_auto_send below, which is the second, execution-time gate).
    """
    text = f"{ticket_subject} {ticket_body}".lower()

    if category in ALWAYS_ESCALATE_CATEGORIES:
        return "support.manage"
    if any(keyword in text for keyword in ALWAYS_ESCALATE_KEYWORDS):
        return "support.manage"
    return "email.manage"


def should_auto_send(draft_confidence: float) -> bool:
    """
    Pure function, used at EXECUTION time, after a reply has actually
    been drafted. This is the second gate: even a ticket whose category/
    keywords passed choose_submit_action's screen (action="email.manage",
    not forced to review) should NOT be auto-sent if the draft itself
    came back low-confidence. In that case the worker should report
    status="escalated" instead of actually sending — see worker.py.
    Self-escalating is always allowed regardless of what action a job
    was submitted under; only auto-SENDING requires clearing this bar.
    """
    return draft_confidence >= MIN_CONFIDENCE_FOR_AUTO_SEND


def assert_action_is_safe(action: str) -> None:
    """
    Defense in depth: raises if something ever tries to use an action
    outside this employee's permitted set or inside the global denylist.
    choose_action() above can only produce safe outputs by construction,
    but any other code path that might submit a job (discovery.py,
    future task types) should call this before submitting, so a bug
    there fails loudly instead of silently reaching the server with a
    bad action (which the server would also reject, but failing here is
    faster to diagnose and doesn't burn a wasted round trip).
    """
    if action in AI_GLOBAL_DENYLIST:
        raise ValueError(f"Action {action!r} is on the global AI denylist — refusing to submit.")
    if action not in PERMITTED_ACTIONS:
        raise ValueError(f"Action {action!r} is not in this employee's permitted_actions — refusing to submit.")
