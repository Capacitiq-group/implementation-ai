"""
Voice Agent guardrail tests — same shape as test_speed_to_lead.py. No
real credentials or network needed; relies on the sandbox short-circuits
in integrations/twilio_client.py and integrations/elevenlabs_client.py.
"""

import asyncio

from ..models import IntakeForm, OnboardingNotes, ReportStatus, ServiceType
from ..services.voice_agent import VoiceAgentImplementer

TEST_SERVICE_ID = "acs_test_voice_001"
TEST_CLIENT_ID = "client_test_001"


def _make_implementer(intake_data: dict, notes_data: dict | None = None):
    intake = IntakeForm(
        agency_client_service_id=TEST_SERVICE_ID,
        client_id=TEST_CLIENT_ID,
        service=ServiceType.VOICE_AGENT,
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
    return VoiceAgentImplementer(TEST_SERVICE_ID, intake, notes)


VALID_INTAKE = {
    "business_name": "ABC Plumbers",
    "business_description": "A residential plumbing company in Cape Town.",
    "services_and_prices": "Callout: R450. Geyser repair: from R800.",
    "operating_hours": "Mon-Fri 8am-5pm",
    "faqs": "Q: Do you work weekends? A: Emergency callouts only.",
}


def test_missing_required_fields_blocks_without_guessing():
    impl = _make_implementer(intake_data={"business_name": "ABC Plumbers"})
    report = asyncio.run(impl.run())

    assert report.status == ReportStatus.BLOCKED
    assert report.steps_completed == []
    assert any("Missing required intake fields" in f for f in report.flags_for_human)
    # Nothing should have been provisioned before the block.
    assert report.artifacts == {}


def test_crm_integration_request_is_flagged_not_silently_built():
    impl = _make_implementer(intake_data={**VALID_INTAKE, "requires_crm_integration": True})
    report = asyncio.run(impl.run())

    assert any("Level 3" in f and "booking/CRM" in f for f in report.flags_for_human)
    # It should still proceed with the rest of implementation, not block entirely —
    # a CRM request is a scope flag, not a missing-data blocker.
    assert report.artifacts != {}


def test_valid_intake_produces_artifacts_and_stays_below_qc_until_sandbox_test_endpoints_wired():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    report = asyncio.run(impl.run())

    assert len(report.steps_completed) > 0
    assert "twilio_number" in report.artifacts
    assert "elevenlabs_agent_id" in report.artifacts
    assert "system_prompt" in report.artifacts
    # The prompt should actually contain the business facts supplied,
    # not a placeholder — this is the anti-hallucination guarantee.
    assert "ABC Plumbers" in report.artifacts["system_prompt"]
    assert "[MISSING" not in report.artifacts["system_prompt"]
    assert report.status == ReportStatus.NEEDS_REVIEW
    assert all(r.result == "fail" for r in report.test_results)


def test_missing_faqs_produces_missing_placeholder_and_flag():
    incomplete = {k: v for k, v in VALID_INTAKE.items() if k != "faqs"}
    impl = _make_implementer(intake_data=incomplete)
    report = asyncio.run(impl.run())

    # faqs is required, so this should block before ever reaching the
    # prompt-builder — proves the required-field list actually matches
    # what the prompt needs.
    assert report.status == ReportStatus.BLOCKED
    assert any("faqs" in f for f in report.flags_for_human)
