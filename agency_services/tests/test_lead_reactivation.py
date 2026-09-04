"""
Two levels of proof here, deliberately separated:

1. test_suppression_list_logic — the compliance rule itself
   (filter_suppressed_contacts) is a pure function, tested directly with
   zero mocking. This is the strongest kind of proof: no network, no
   assumptions about what a mock returns — just the actual filtering
   logic against real inputs.
2. test_lead_reactivation implementer tests — mock only the network call
   (get_suppressed_emails) to prove implement() wires that pure logic in
   correctly end to end.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from ..integrations.suppression_list import filter_suppressed_contacts
from ..models import IntakeForm, OnboardingNotes, ReportStatus, ServiceType
from ..services.lead_reactivation import LeadReactivationImplementer

TEST_SERVICE_ID = "acs_test_reactivation_001"
TEST_CLIENT_ID = "client_test_001"


# --- 1. Pure logic, no mocking, no network -------------------------------

def test_suppression_list_logic_excludes_only_suppressed_emails():
    contacts = [
        {"email": "alice@example.com", "name": "Alice"},
        {"email": "bob@example.com", "name": "Bob"},
        {"email": "carol@example.com", "name": "Carol"},
    ]
    suppressed_emails = {"bob@example.com"}

    allowed, suppressed = filter_suppressed_contacts(contacts, suppressed_emails)

    assert [c["email"] for c in allowed] == ["alice@example.com", "carol@example.com"]
    assert [c["email"] for c in suppressed] == ["bob@example.com"]


def test_suppression_list_logic_is_case_insensitive():
    contacts = [{"email": "Bob@Example.com", "name": "Bob"}]
    suppressed_emails = {"bob@example.com"}

    allowed, suppressed = filter_suppressed_contacts(contacts, suppressed_emails)

    assert allowed == []
    assert len(suppressed) == 1


def test_suppression_list_logic_reapplies_on_reupload():
    """The core compliance guarantee: re-uploading the same list doesn't
    let a suppressed contact back in — this function has no memory of
    "already checked," it re-derives the answer from the current
    suppression set every time it's called, which is exactly what makes
    that guarantee hold."""
    contacts = [{"email": "bob@example.com", "name": "Bob"}]
    suppressed_emails = {"bob@example.com"}

    first_run_allowed, _ = filter_suppressed_contacts(contacts, suppressed_emails)
    second_run_allowed, _ = filter_suppressed_contacts(contacts, suppressed_emails)  # same list, re-uploaded

    assert first_run_allowed == []
    assert second_run_allowed == []


# --- 2. Implementer tests, mocking only the network boundary -------------

def _make_implementer(intake_data: dict, notes_data: dict | None = None):
    intake = IntakeForm(
        agency_client_service_id=TEST_SERVICE_ID,
        client_id=TEST_CLIENT_ID,
        service=ServiceType.LEAD_REACTIVATION,
        plan_tier="standard",
        data=intake_data,
    )
    notes = OnboardingNotes(
        agency_client_service_id=TEST_SERVICE_ID,
        client_id=TEST_CLIENT_ID,
        call_held_at=None,
        notes="",
        additional_info=notes_data or {},
    )
    return LeadReactivationImplementer(TEST_SERVICE_ID, intake, notes)


VALID_INTAKE = {
    "business_name": "ABC Plumbers",
    "contacts": [
        {"email": "alice@example.com", "name": "Alice"},
        {"email": "bob@example.com", "name": "Bob"},
        {"email": "carol@example.com", "name": "Carol"},
    ],
    "personalisation_rules": "Mention it's been a while since their last service.",
    "outreach_rules": "One email, no follow-up sequence yet.",
    "reactivation_offer_or_reason": "10% off their next callout, valid this month.",
}


def test_missing_required_fields_blocks_without_guessing():
    impl = _make_implementer(intake_data={"business_name": "ABC Plumbers"})
    with patch(
        "agency_services.services.lead_reactivation.get_suppressed_emails",
        new=AsyncMock(return_value=set()),
    ):
        report = asyncio.run(impl.run())

    assert report.status == ReportStatus.BLOCKED
    assert report.artifacts == {}
    assert any("Missing required intake fields" in f for f in report.flags_for_human)


def test_suppressed_contact_excluded_end_to_end():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    with patch(
        "agency_services.services.lead_reactivation.get_suppressed_emails",
        new=AsyncMock(return_value={"bob@example.com"}),
    ):
        report = asyncio.run(impl.run())

    assert report.artifacts["contacts_total"] == 3
    assert report.artifacts["contacts_suppressed"] == 1
    assert report.artifacts["contacts_allowed"] == 2
    assert any("1 contact(s) were excluded" in f for f in report.flags_for_human)
    # The suppression self-test scenario should report the real count, not a placeholder.
    suppression_result = next(r for r in report.test_results if r.name == "suppression_list_enforced")
    assert suppression_result.result == "pass"
    assert "1 of 3" in suppression_result.detail


def test_all_contacts_suppressed_blocks_rather_than_running_empty_campaign():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    with patch(
        "agency_services.services.lead_reactivation.get_suppressed_emails",
        new=AsyncMock(return_value={"alice@example.com", "bob@example.com", "carol@example.com"}),
    ):
        report = asyncio.run(impl.run())

    assert report.status == ReportStatus.BLOCKED
    assert any("no campaign to run" in f for f in report.flags_for_human)


def test_valid_intake_produces_grounded_prompt_no_missing_placeholders():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    with patch(
        "agency_services.services.lead_reactivation.get_suppressed_emails",
        new=AsyncMock(return_value=set()),
    ):
        report = asyncio.run(impl.run())

    assert "ABC Plumbers" in report.artifacts["personalisation_prompt"]
    assert "[MISSING" not in report.artifacts["personalisation_prompt"]
    assert report.artifacts["channel"] == "email"
    assert report.status == ReportStatus.NEEDS_REVIEW  # personalisation self-test not wired yet
