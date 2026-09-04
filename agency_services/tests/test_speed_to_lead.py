"""
Unit tests that run with NO real credentials and NO network access —
they verify the guardrail logic (missing-field blocking, out-of-scope
lead-source flagging), using the sandbox short-circuit already built
into integrations/twilio_client.py and integrations/elevenlabs_client.py
(both return synthetic data when ENVIRONMENT=sandbox, the default).

Once real sandbox credentials exist, add a second test file
(test_speed_to_lead_integration.py) that exercises these against actual
sandbox Twilio/ElevenLabs — keep that separate so CI can run the fast
guardrail tests without any credentials present.
"""

import asyncio

from ..models import IntakeForm, OnboardingNotes, ReportStatus, ServiceType
from ..services.speed_to_lead import SpeedToLeadImplementer

TEST_SERVICE_ID = "acs_test_001"
TEST_CLIENT_ID = "client_test_001"


def _make_implementer(intake_data: dict, notes_data: dict | None = None):
    intake = IntakeForm(
        agency_client_service_id=TEST_SERVICE_ID,
        client_id=TEST_CLIENT_ID,
        service=ServiceType.SPEED_TO_LEAD,
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
    return SpeedToLeadImplementer(TEST_SERVICE_ID, intake, notes)


def test_missing_required_fields_blocks_without_guessing():
    impl = _make_implementer(intake_data={"business_name": "ABC Plumbers"})
    report = asyncio.run(impl.run())

    assert report.status == ReportStatus.BLOCKED
    assert report.agency_client_service_id == TEST_SERVICE_ID
    assert report.client_id == TEST_CLIENT_ID
    assert report.steps_completed == []
    assert any("Missing required intake fields" in f for f in report.flags_for_human)


def test_out_of_scope_lead_source_is_flagged_not_silently_configured():
    impl = _make_implementer(intake_data={
        "business_name": "ABC Plumbers",
        "lead_source": ["website_form", "google_ads_form"],  # google_ads_form not in allowed set
        "qualifying_questions": "What's the issue? When do you need it fixed?",
        "qualification_criteria": "Qualified if urgent and in service area.",
    })
    report = asyncio.run(impl.run())

    assert any("google_ads_form" in f and "Level 3" in f for f in report.flags_for_human)


def test_valid_intake_produces_artifacts_and_stays_below_qc_until_sandbox_test_endpoints_wired():
    impl = _make_implementer(intake_data={
        "business_name": "ABC Plumbers",
        "lead_source": ["website_form"],
        "qualifying_questions": "What's the issue? When do you need it fixed?",
        "qualification_criteria": "Qualified if urgent and in service area.",
    })
    report = asyncio.run(impl.run())

    assert len(report.steps_completed) > 0
    # implement() ran against the sandbox short-circuits in
    # integrations/twilio_client.py + elevenlabs_client.py, so artifacts
    # should be populated even without real credentials.
    assert "twilio_number" in report.artifacts
    assert "elevenlabs_agent_id" in report.artifacts
    # Self-test scenarios still fail because those TODOs aren't wired to
    # a live/sandbox test endpoint yet — expected and correct for now.
    assert report.status == ReportStatus.NEEDS_REVIEW
    assert all(r.result == "fail" for r in report.test_results)
