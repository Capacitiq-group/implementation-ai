"""
Custom Agentic AI Employee guardrail tests — same shape as the other
three services' test files. No real credentials or network needed.
"""

import asyncio

from ..models import IntakeForm, OnboardingNotes, ReportStatus, ServiceType
from ..services.custom_agentic_employee import CustomAgenticEmployeeImplementer

TEST_SERVICE_ID = "acs_test_agentic_001"
TEST_CLIENT_ID = "client_test_001"


def _make_implementer(intake_data: dict, notes_data: dict | None = None):
    intake = IntakeForm(
        agency_client_service_id=TEST_SERVICE_ID,
        client_id=TEST_CLIENT_ID,
        service=ServiceType.CUSTOM_AGENTIC_EMPLOYEE,
        plan_tier="advanced",
        data=intake_data,
    )
    notes = OnboardingNotes(
        agency_client_service_id=TEST_SERVICE_ID,
        client_id=TEST_CLIENT_ID,
        call_held_at=None,
        notes="",
        additional_info=notes_data or {},
    )
    return CustomAgenticEmployeeImplementer(TEST_SERVICE_ID, intake, notes)


VALID_INTAKE = {
    "role": "Invoice triage assistant",
    "responsibilities": "Classify incoming supplier invoices and route them to the right approver.",
    "decision_rules": "Route by amount: under R5000 to line manager, over R5000 to finance director.",
    "escalation_rules": "Any invoice with a mismatched PO number goes to a human, no exceptions.",
    "tool_permissions": ["read_invoice_inbox", "create_approval_task"],
}


def test_missing_discovery_fields_blocks_without_guessing():
    impl = _make_implementer(intake_data={"role": "Invoice triage assistant"})
    report = asyncio.run(impl.run())

    assert report.status == ReportStatus.BLOCKED
    assert report.artifacts == {}
    assert any("Missing required discovery-output fields" in f for f in report.flags_for_human)


def test_missing_tool_permissions_flagged_not_assumed():
    incomplete = {k: v for k, v in VALID_INTAKE.items() if k != "tool_permissions"}
    impl = _make_implementer(intake_data=incomplete)
    report = asyncio.run(impl.run())

    assert report.status != ReportStatus.BLOCKED  # missing tools is a flag, not a blocker
    assert any("No tool_permissions specified" in f for f in report.flags_for_human)
    assert report.artifacts["tool_permissions"] == []
    # The prompt should explicitly deny access, not silently omit the section.
    assert "MISSING" in report.artifacts["system_prompt"] or "no tool permissions" in report.artifacts["system_prompt"].lower()


def test_valid_intake_encodes_mandatory_guardrails_in_prompt():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    report = asyncio.run(impl.run())

    prompt = report.artifacts["system_prompt"]
    assert "[MISSING" not in prompt
    assert "Invoice triage assistant" in prompt
    assert "under R5000" in prompt  # client-specific decision rule made it in
    # The mandatory, never-client-specific guardrail sections must be present
    # regardless of what's bespoke.
    assert "NEVER DO" in prompt.upper()
    assert "REQUIRES HUMAN APPROVAL" in prompt.upper()
    assert "SECURITY REQUIREMENTS" in prompt.upper()


def test_standing_human_review_flag_always_present_on_success():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    report = asyncio.run(impl.run())

    assert any("always warrant a careful human read" in f for f in report.flags_for_human)


def test_self_test_includes_approval_and_permission_boundary_scenarios():
    impl = _make_implementer(intake_data=VALID_INTAKE)
    report = asyncio.run(impl.run())

    scenario_names = {r.name for r in report.test_results}
    assert "approval_required_action_stops_and_asks" in scenario_names
    assert "permission_boundary_probe" in scenario_names
    assert len(report.test_results) == 5
