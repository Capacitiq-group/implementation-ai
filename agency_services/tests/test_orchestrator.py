"""
Verifies the persistence behaviour added for agency_service_configs —
not just that the code compiles, but that run_implementation actually
calls upsert with the right collection and payload. Mocks the PocketBase
client entirely (no real network) since this container can't reach a
real instance.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from ..models import OnboardingStatus, ServiceType

FAKE_SERVICE_RECORD = {
    "id": "acs_test_001",
    "agency_client_id": "client_test_001",
    "service_slug": "speed_to_lead",
    "tier": "standard",
    "onboarding_status": "onboarding_notes_ready",
}

FAKE_INTAKE = {
    "agency_client_service_id": "acs_test_001",
    "data": {
        "business_name": "ABC Plumbers",
        "lead_source": ["website_form"],
        "qualifying_questions": "What's the issue?",
        "qualification_criteria": "Qualified if urgent.",
    },
}

FAKE_NOTES = {
    "agency_client_service_id": "acs_test_001",
    "call_held_at": None,
    "notes": "",
    "additional_info": {},
}


def _fake_get_record(collection, filter_expr):
    if collection == "agency_client_services":
        return FAKE_SERVICE_RECORD
    if collection == "intake_forms":
        return FAKE_INTAKE
    if collection == "onboarding_notes":
        return FAKE_NOTES
    if collection == "agency_service_configs":
        return None  # first run — no existing config, upsert should create
    raise AssertionError(f"Unexpected get_record call: {collection}")


def test_run_implementation_persists_config_to_agency_service_configs():
    from .. import orchestrator

    with patch.object(orchestrator, "pocketbase") as mock_pb:
        mock_pb.get_record = AsyncMock(side_effect=_fake_get_record)
        mock_pb.update_record = AsyncMock(return_value={})
        mock_pb.create_record = AsyncMock(return_value={})
        mock_pb.upsert_record = AsyncMock(return_value={})

        asyncio.run(orchestrator.run_implementation("acs_test_001"))

        # onboarding_status should have been flipped to implementing, then
        # to pending_qc (valid intake -> not blocked).
        status_updates = [
            call.args[2]["onboarding_status"]
            for call in mock_pb.update_record.call_args_list
            if call.args[0] == "agency_client_services"
        ]
        assert OnboardingStatus.IMPLEMENTING in status_updates
        assert OnboardingStatus.PENDING_QC in status_updates
        assert OnboardingStatus.ACTIVE not in status_updates  # never sets active — admin-only

        # implementation_reports must have been created.
        report_calls = [c for c in mock_pb.create_record.call_args_list if c.args[0] == "implementation_reports"]
        assert len(report_calls) == 1

        # agency_service_configs must have been upserted with the real
        # artifacts (twilio_number, elevenlabs_agent_id) from implement().
        assert mock_pb.upsert_record.call_count == 1
        config_call = mock_pb.upsert_record.call_args
        assert config_call.args[0] == "agency_service_configs"
        assert config_call.args[1] == "agency_client_service_id='acs_test_001'"
        payload = config_call.args[2]
        assert payload["agency_client_service_id"] == "acs_test_001"
        assert payload["client_id"] == "client_test_001"
        assert "twilio_number" in payload["config"]
        assert "elevenlabs_agent_id" in payload["config"]
