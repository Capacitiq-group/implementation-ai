"""
Suppression/opt-out list for Lead Reactivation. Unlike package_boundaries.py,
this is NOT short-circuited in sandbox — the compliance rule (a contact
who opted out must never re-enter a campaign, even on re-upload) is
exactly what testing needs to prove works, so it always does a real
query. `agency_suppressed_contacts` is a new collection — see
ARCHITECTURE-ADDENDUM.

Split into a network call (get_suppressed_emails) and a pure function
(filter_suppressed_contacts) on purpose: the pure function is what
actually enforces the compliance rule and is fully unit-testable with no
mocking at all; the network call is what test_lead_reactivation.py mocks,
same pattern as test_orchestrator.py.
"""

from .pocketbase_client import pocketbase


async def get_suppressed_emails(client_id: str) -> set[str]:
    """One query for the whole suppression list, not one per contact."""
    records = await pocketbase.list_records(
        "agency_suppressed_contacts", filter_expr=f"client_id='{client_id}'"
    )
    return {r["contact_email"].lower() for r in records if r.get("contact_email")}


def filter_suppressed_contacts(
    contacts: list[dict], suppressed_emails: set[str]
) -> tuple[list[dict], list[dict]]:
    """
    Pure function, no I/O — this is the actual compliance-rule
    enforcement. contacts is a list of dicts each expected to have an
    "email" key. Returns (allowed, suppressed).
    """
    allowed: list[dict] = []
    suppressed: list[dict] = []
    for contact in contacts:
        email = (contact.get("email") or "").strip().lower()
        if email and email in suppressed_emails:
            suppressed.append(contact)
        else:
            allowed.append(contact)
    return allowed, suppressed
