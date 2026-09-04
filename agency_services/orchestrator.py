"""
Top-level orchestrator. Called when an agency_client_services record's
onboarding_status moves to implementation_triggered (always a manual
admin action, never automatic on payment).

Corrected per ARCHITECTURE.md §3/§4: keyed by agency_client_service_id,
not client_id — onboarding happens per purchased service. Respects the
exact CRUD table in that doc:
  - clients: read-only, own-client-scoped (used here only for minimal
    context if needed — not written).
  - agency_client_services: read own-service-scoped; write ONLY
    onboarding_status (implementation_triggered -> implementing ->
    pending_qc). Never touches `status`, `tier`, pricing, or anything
    else on this collection.
  - intake_forms / onboarding_notes: read-only, primary input.
  - implementation_reports: this agent's own collection — create + read
    own + update (progress updates).
"""

from .integrations.pocketbase_client import pocketbase
from .models import (
    ImplementationReport,
    IntakeForm,
    OnboardingNotes,
    OnboardingStatus,
    ServiceType,
)
from .services.base import ServiceImplementer
from .services.custom_agentic_employee import CustomAgenticEmployeeImplementer
from .services.lead_reactivation import LeadReactivationImplementer
from .services.speed_to_lead import SpeedToLeadImplementer
from .services.voice_agent import VoiceAgentImplementer

IMPLEMENTERS: dict[ServiceType, type[ServiceImplementer]] = {
    ServiceType.VOICE_AGENT: VoiceAgentImplementer,
    ServiceType.SPEED_TO_LEAD: SpeedToLeadImplementer,
    ServiceType.LEAD_REACTIVATION: LeadReactivationImplementer,
    ServiceType.CUSTOM_AGENTIC_EMPLOYEE: CustomAgenticEmployeeImplementer,
}


async def run_implementation(agency_client_service_id: str) -> None:
    """
    Entry point, called from main.py's /implementation/trigger as a
    background task. main.py already checks onboarding_status ==
    onboarding_notes_ready before scheduling this — this function assumes
    that sequencing already happened.
    """
    service_record = await pocketbase.get_record(
        "agency_client_services", f"id='{agency_client_service_id}'"
    )
    if service_record is None:
        raise ValueError(f"No agency_client_services record found for {agency_client_service_id!r}")

    client_id = service_record["agency_client_id"]

    intake_record = await pocketbase.get_record(
        "intake_forms", f"agency_client_service_id='{agency_client_service_id}'"
    )
    notes_record = await pocketbase.get_record(
        "onboarding_notes", f"agency_client_service_id='{agency_client_service_id}'"
    )

    intake = IntakeForm(
        agency_client_service_id=agency_client_service_id,
        client_id=client_id,
        service=ServiceType(service_record["service_slug"]),
        plan_tier=service_record["tier"],
        data=(intake_record or {}).get("data", {}),
    )
    notes = OnboardingNotes(
        agency_client_service_id=agency_client_service_id,
        client_id=client_id,
        call_held_at=(notes_record or {}).get("call_held_at"),
        notes=(notes_record or {}).get("notes", ""),
        additional_info=(notes_record or {}).get("additional_info", {}),
    )

    await pocketbase.update_record(
        "agency_client_services", agency_client_service_id,
        {"onboarding_status": OnboardingStatus.IMPLEMENTING},
    )

    implementer_cls = IMPLEMENTERS[intake.service]
    implementer = implementer_cls(agency_client_service_id, intake, notes)
    report: ImplementationReport = await implementer.run()

    await pocketbase.create_record("implementation_reports", {
        "agency_client_service_id": report.agency_client_service_id,
        "client_id": report.client_id,
        "service": report.service.value if hasattr(report.service, "value") else report.service,
        "status": report.status.value if hasattr(report.status, "value") else report.status,
        "steps_completed": report.steps_completed,
        "test_results": [r.__dict__ for r in report.test_results],
        "flags_for_human": report.flags_for_human,
        "artifacts": report.artifacts,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    })

    # Persist current live config so synkra-core's runtime side has
    # somewhere real to read it from — this agent's write-scope on
    # agency_client_services covers onboarding_status only (ARCHITECTURE.md
    # §3), so config lives here instead, upserted so re-implementation
    # overwrites rather than accumulates.
    if report.artifacts:
        await pocketbase.upsert_record(
            "agency_service_configs",
            f"agency_client_service_id='{agency_client_service_id}'",
            {
                "agency_client_service_id": agency_client_service_id,
                "client_id": client_id,
                "service": intake.service.value,
                "config": report.artifacts,
                "updated_at": report.completed_at.isoformat() if report.completed_at else None,
            },
        )

    # Bounce back to onboarding_notes_ready if blocked (needs a human to
    # fill a gap, not QC yet) — otherwise advance to pending_qc. Never
    # sets `active`; that's admin-only (ARCHITECTURE.md §5).
    new_status = (
        OnboardingStatus.PENDING_QC
        if report.status != "blocked"
        else OnboardingStatus.ONBOARDING_NOTES_READY
    )
    await pocketbase.update_record(
        "agency_client_services", agency_client_service_id,
        {"onboarding_status": new_status},
    )
