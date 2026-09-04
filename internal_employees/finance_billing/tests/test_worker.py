import asyncio
from unittest.mock import AsyncMock, patch

from .. import worker


SERVICE = {
    "id": "acs1",
    "agency_client_id": "client1",
    "service_slug": "speed_to_lead",
    "tier": "standard",
    "setup_price": 5000.0,
    "monthly_price": 1500.0,
}
CLIENT = {"id": "client1", "contact_email": "owner@example.com", "contact_name": "Jane Owner"}


def _patch_all(mock_pb, mock_zoho=None):
    """Patches worker's own pocketbase/zoho references AND discovery's
    own pocketbase reference — discovery.py imports the singleton
    independently, so patching worker.pocketbase alone leaves discovery
    still pointed at the real (network-requiring) object."""
    patches = [
        patch.object(worker, "pocketbase", mock_pb),
        patch.object(worker.discovery, "pocketbase", mock_pb),
    ]
    if mock_zoho is not None:
        patches.append(patch.object(worker, "zoho", mock_zoho))
    return patches


def _apply(patches):
    for p in patches:
        p.start()
    return patches


def _stop(patches):
    for p in patches:
        p.stop()


def test_draft_quotes_happy_path_creates_estimate_and_drafted_document():
    mock_pb = AsyncMock()
    mock_zoho = AsyncMock()

    async def fake_list_records(collection, filter_expr="", per_page=200, sort=""):
        if collection == "agency_client_services":
            return [SERVICE]
        if collection == "agency_billing_documents":
            return []  # no existing quotes
        return []
    mock_pb.list_records = AsyncMock(side_effect=fake_list_records)

    async def fake_get_record(collection, filter_expr):
        if collection == "clients":
            return CLIENT
        if collection == "service_packages":
            return {"boundaries": {"included_every_tier": ["90 second response"]}}
        return None
    mock_pb.get_record = AsyncMock(side_effect=fake_get_record)
    mock_pb.create_record = AsyncMock(return_value={})

    mock_zoho.find_or_create_contact = AsyncMock(return_value="zoho_contact_1")
    mock_zoho.create_draft_estimate = AsyncMock(return_value={
        "estimate_id": "zoho_est_1", "total": 6500.0, "currency_code": "ZAR",
    })

    patches = _apply(_patch_all(mock_pb, mock_zoho))
    try:
        results = asyncio.run(worker.draft_quotes())
    finally:
        _stop(patches)

    assert len(results) == 1
    assert results[0]["status"] == "drafted"
    assert results[0]["zoho_estimate_id"] == "zoho_est_1"
    mock_zoho.find_or_create_contact.assert_called_once_with("Jane Owner", "owner@example.com")
    created_call = mock_pb.create_record.call_args
    assert created_call.args[0] == "agency_billing_documents"
    assert created_call.args[1]["status"] == "drafted"


def test_draft_quotes_skips_services_that_already_have_a_quote():
    mock_pb = AsyncMock()
    mock_zoho = AsyncMock()

    async def fake_list_records(collection, filter_expr="", per_page=200, sort=""):
        if collection == "agency_client_services":
            return [SERVICE]
        if collection == "agency_billing_documents":
            return [{"agency_client_service_id": "acs1"}]  # already quoted
        return []
    mock_pb.list_records = AsyncMock(side_effect=fake_list_records)

    patches = _apply(_patch_all(mock_pb, mock_zoho))
    try:
        results = asyncio.run(worker.draft_quotes())
    finally:
        _stop(patches)

    assert results == []
    mock_zoho.find_or_create_contact.assert_not_called()


def test_draft_quotes_writes_blocked_document_when_client_missing():
    mock_pb = AsyncMock()
    mock_zoho = AsyncMock()

    async def fake_list_records(collection, filter_expr="", per_page=200, sort=""):
        if collection == "agency_client_services":
            return [SERVICE]
        return []
    mock_pb.list_records = AsyncMock(side_effect=fake_list_records)
    mock_pb.get_record = AsyncMock(return_value=None)  # no client found
    mock_pb.create_record = AsyncMock(return_value={})

    patches = _apply(_patch_all(mock_pb, mock_zoho))
    try:
        asyncio.run(worker.draft_quotes())
    finally:
        _stop(patches)

    mock_zoho.find_or_create_contact.assert_not_called()  # never reached Zoho
    created_call = mock_pb.create_record.call_args
    assert created_call.args[1]["status"] == "blocked"
    assert any("No matching client record" in f for f in created_call.args[1]["flags_for_human"])


def test_draft_quotes_writes_blocked_document_when_pricing_missing():
    unpriced_service = {**SERVICE, "setup_price": None, "monthly_price": None}
    mock_pb = AsyncMock()
    mock_zoho = AsyncMock()

    async def fake_list_records(collection, filter_expr="", per_page=200, sort=""):
        if collection == "agency_client_services":
            return [unpriced_service]
        return []
    mock_pb.list_records = AsyncMock(side_effect=fake_list_records)

    async def fake_get_record(collection, filter_expr):
        if collection == "clients":
            return CLIENT
        return None
    mock_pb.get_record = AsyncMock(side_effect=fake_get_record)
    mock_pb.create_record = AsyncMock(return_value={})

    patches = _apply(_patch_all(mock_pb, mock_zoho))
    try:
        asyncio.run(worker.draft_quotes())
    finally:
        _stop(patches)

    mock_zoho.find_or_create_contact.assert_not_called()
    created_call = mock_pb.create_record.call_args
    assert created_call.args[1]["status"] == "blocked"
    assert any("no setup_price or" in f for f in created_call.args[1]["flags_for_human"])


def test_sync_document_statuses_updates_on_change_and_skips_unmapped():
    mock_pb = AsyncMock()
    mock_zoho = AsyncMock()

    sent_docs = [
        {"id": "doc1", "document_type": "quote", "zoho_estimate_id": "est1", "status": "sent"},
        {"id": "doc2", "document_type": "invoice", "zoho_invoice_id": "inv1", "status": "sent"},
    ]

    async def fake_list_records(collection, filter_expr="", per_page=200, sort=""):
        if collection == "agency_billing_documents":
            return sent_docs
        return []
    mock_pb.list_records = AsyncMock(side_effect=fake_list_records)
    mock_pb.update_record = AsyncMock(return_value={})

    mock_zoho.get_estimate_status = AsyncMock(return_value="accepted")
    mock_zoho.get_invoice_status = AsyncMock(return_value="paid")

    patches = _apply(_patch_all(mock_pb, mock_zoho))
    try:
        checked = asyncio.run(worker.sync_document_statuses())
    finally:
        _stop(patches)

    assert checked == 2
    assert mock_pb.update_record.call_count == 2
    update_calls = {c.args[1]: c.args[2]["status"] for c in mock_pb.update_record.call_args_list}
    assert update_calls["doc1"] == "accepted"
    assert update_calls["doc2"] == "paid"


def test_sync_document_statuses_does_not_update_when_status_unchanged():
    mock_pb = AsyncMock()
    mock_zoho = AsyncMock()

    async def fake_list_records(collection, filter_expr="", per_page=200, sort=""):
        if collection == "agency_billing_documents":
            return [{"id": "doc1", "document_type": "quote", "zoho_estimate_id": "est1", "status": "sent"}]
        return []
    mock_pb.list_records = AsyncMock(side_effect=fake_list_records)
    mock_pb.update_record = AsyncMock(return_value={})
    mock_zoho.get_estimate_status = AsyncMock(return_value="sent")  # unchanged (maps to "sent")

    patches = _apply(_patch_all(mock_pb, mock_zoho))
    try:
        asyncio.run(worker.sync_document_statuses())
    finally:
        _stop(patches)

    mock_pb.update_record.assert_not_called()


def test_map_zoho_status_covers_every_known_status():
    assert worker._map_zoho_status("accepted") == "accepted"
    assert worker._map_zoho_status("declined") == "declined"
    assert worker._map_zoho_status("expired") == "declined"
    assert worker._map_zoho_status("paid") == "paid"
    assert worker._map_zoho_status("overdue") == "overdue"
    assert worker._map_zoho_status("sent") == "sent"
    assert worker._map_zoho_status("viewed") == "sent"


def test_map_zoho_status_returns_none_for_unrecognized_status_rather_than_guessing():
    assert worker._map_zoho_status("some_new_zoho_status_not_yet_mapped") is None
