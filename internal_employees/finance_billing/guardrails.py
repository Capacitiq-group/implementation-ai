"""
Small, focused guardrails for this employee. The main risk this codebase
already established a pattern for — never let an AI unilaterally commit
the business to something — applies here as: never send a financial
document automatically. That's enforced structurally in
integrations/zoho.py (create_draft_estimate never passes `send`), but
assert_never_marked_sent below is a second, independent check worker.py
calls before writing any record, so a future code change to worker.py
can't accidentally start marking things "sent" without this failing
loudly.
"""

from datetime import date, timedelta

DEFAULT_QUOTE_VALIDITY_DAYS = 30


def default_expiry_date(from_date: date | None = None) -> str:
    """Pure function. Returns an ISO date string DEFAULT_QUOTE_VALIDITY_DAYS
    from from_date (or today)."""
    base = from_date or date.today()
    return (base + timedelta(days=DEFAULT_QUOTE_VALIDITY_DAYS)).isoformat()


def assert_never_marked_sent(document_status: str) -> None:
    """This employee only ever writes agency_billing_documents with
    status "drafted" or "blocked" — never "sent", "accepted", "paid", etc.
    Those transitions are for a human (or a Zoho webhook/status-sync
    pass) to make, not this employee's own drafting step."""
    if document_status not in ("drafted", "blocked"):
        raise ValueError(
            f"Refusing to write agency_billing_documents with status "
            f"{document_status!r} from the drafting step — this employee "
            f"only ever drafts, it never marks something sent/accepted/paid."
        )
