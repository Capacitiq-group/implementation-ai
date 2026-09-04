"""
Finds agency_client_services records that don't have a "quote" type
agency_billing_documents record yet — same discovery-dedup shape as
customer_support's ticket discovery. Does not touch agency_client_services
itself (no write access needed for discovery, same as the other
employees' read-only discovery passes).
"""

from .integrations.pocketbase import pocketbase


async def find_services_needing_a_quote() -> list[dict]:
    services = await pocketbase.list_records("agency_client_services", sort="+created")
    if not services:
        return []

    existing_quotes = await pocketbase.list_records(
        "agency_billing_documents", filter_expr="document_type = 'quote'"
    )
    service_ids_with_quotes = {d.get("agency_client_service_id") for d in existing_quotes}

    return [s for s in services if s["id"] not in service_ids_with_quotes]


async def find_sent_documents_needing_status_check() -> list[dict]:
    """Documents already sent (by a human, after this employee drafted
    them) that haven't reached a terminal status yet — these get
    periodically re-checked against Zoho to catch acceptance/payment."""
    return await pocketbase.list_records(
        "agency_billing_documents",
        filter_expr="status = 'sent'",
    )
