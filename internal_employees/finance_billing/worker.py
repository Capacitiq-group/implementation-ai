"""
Main loop for the Finance & Billing employee.

Two responsibilities per cycle:
1. draft_quotes() — find agency_client_services with no quote yet, draft
   one in Zoho (as a draft, never sent — see integrations/zoho.py),
   record it in agency_billing_documents.
2. sync_document_statuses() — for documents already marked "sent" (by a
   human, outside this employee's own actions), re-check Zoho and update
   the local status if it's moved (accepted/declined/paid/overdue).
"""

from .._framework.worker_loop import run_forever as loop_forever

from . import discovery, guardrails, packages
from .config import settings
from .integrations import zoho
from .integrations.pocketbase import pocketbase


async def draft_quotes() -> list[dict]:
    services = await discovery.find_services_needing_a_quote()
    results = []

    for service in services:
        client = await pocketbase.get_record("clients", f"id = '{service.get('agency_client_id')}'")
        if not client:
            await _write_blocked_document(service, [f"No matching client record for agency_client_id={service.get('agency_client_id')!r}."])
            continue

        package_record = await pocketbase.get_record(
            "service_packages",
            f"service = '{service.get('service_slug')}' && tier = '{service.get('tier')}'",
        )
        boundaries = (package_record or {}).get("boundaries")

        try:
            line_items = packages.build_quote_line_items(service, boundaries)
        except ValueError as exc:
            await _write_blocked_document(service, [str(exc)])
            continue

        contact_email = client.get("contact_email")
        contact_name = client.get("contact_name") or client.get("company_name")
        if not contact_email:
            await _write_blocked_document(service, [f"Client {client.get('id')} has no contact_email — cannot create a Zoho contact."])
            continue

        contact_id = await zoho.find_or_create_contact(contact_name or contact_email, contact_email)
        estimate = await zoho.create_draft_estimate(
            customer_id=contact_id,
            reference_number=f"{service['id']}",
            expiry_date=guardrails.default_expiry_date(),
            line_items=line_items,
        )

        document = {
            "agency_client_service_id": service["id"],
            "client_id": client["id"],
            "document_type": "quote",
            "zoho_estimate_id": estimate["estimate_id"],
            "status": "drafted",
            "amount_total": estimate.get("total"),
            "currency": estimate.get("currency_code"),
            "line_items": line_items,
            "flags_for_human": [],
        }
        guardrails.assert_never_marked_sent(document["status"])
        await pocketbase.create_record("agency_billing_documents", document)
        results.append(document)

    return results


async def _write_blocked_document(service: dict, flags: list[str]) -> None:
    document = {
        "agency_client_service_id": service["id"],
        "client_id": service.get("agency_client_id", ""),
        "document_type": "quote",
        "status": "blocked",
        "flags_for_human": flags,
    }
    guardrails.assert_never_marked_sent(document["status"])
    await pocketbase.create_record("agency_billing_documents", document)


async def sync_document_statuses() -> int:
    documents = await discovery.find_sent_documents_needing_status_check()
    checked = 0

    for doc in documents:
        if doc.get("document_type") == "quote" and doc.get("zoho_estimate_id"):
            zoho_status = await zoho.get_estimate_status(doc["zoho_estimate_id"])
        elif doc.get("document_type") == "invoice" and doc.get("zoho_invoice_id"):
            zoho_status = await zoho.get_invoice_status(doc["zoho_invoice_id"])
        else:
            continue

        mapped_status = _map_zoho_status(zoho_status)
        if mapped_status and mapped_status != doc.get("status"):
            await pocketbase.update_record("agency_billing_documents", doc["id"], {"status": mapped_status})
        checked += 1

    return checked


def _map_zoho_status(zoho_status: str) -> str | None:
    """Pure function — maps Zoho's own status vocabulary onto ours.
    Returns None for a Zoho status this employee doesn't have a mapping
    for yet, rather than guessing — an unmapped status should surface as
    a gap to fix, not silently coerce into the wrong bucket."""
    mapping = {
        "accepted": "accepted",
        "declined": "declined",
        "expired": "declined",
        "paid": "paid",
        "overdue": "overdue",
        "sent": "sent",
        "viewed": "sent",
    }
    return mapping.get(zoho_status)


async def run_once() -> None:
    await draft_quotes()
    await sync_document_statuses()


async def run_forever() -> None:
    # Loop itself is shared — see _framework/worker_loop.py.
    await loop_forever(run_once, settings.poll_interval_seconds)
