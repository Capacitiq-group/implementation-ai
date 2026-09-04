"""
Data models mirroring the Agency PocketBase collections defined in
ARCHITECTURE.md §3 — that document is now the authoritative schema
reference; this file should be kept in sync with it, not the other way
round.

Correction from the earlier draft: onboarding/implementation pipeline
state lives on `agency_client_services.onboarding_status`, per client
service purchased — NOT on `clients.status`, which is a separate,
company-level field (`active`|`suspended`) unrelated to onboarding. A
client with two purchased services can have one `active` and one still
`implementing` — onboarding is per service, not per client (ARCHITECTURE.md §4).
Every record below is keyed primarily by `agency_client_service_id`, with
`client_id` carried along for read-scoping/context only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OnboardingStatus(str, Enum):
    """Maps to agency_client_services.onboarding_status (ARCHITECTURE.md §3/§4)."""
    QUOTATION_SENT = "quotation_sent"
    INVOICED = "invoiced"
    PAID = "paid"
    INTAKE_FORM_COMPLETED = "intake_form_completed"
    ONBOARDING_SCHEDULED = "onboarding_scheduled"
    ONBOARDING_COMPLETED = "onboarding_completed"
    ONBOARDING_NOTES_READY = "onboarding_notes_ready"
    IMPLEMENTATION_TRIGGERED = "implementation_triggered"
    IMPLEMENTING = "implementing"
    PENDING_QC = "pending_qc"
    ACTIVE = "active"


class ServiceType(str, Enum):
    VOICE_AGENT = "voice_agent"
    SPEED_TO_LEAD = "speed_to_lead"
    LEAD_REACTIVATION = "lead_reactivation"
    CUSTOM_AGENTIC_EMPLOYEE = "custom_agentic_employee"


class ReportStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    READY_FOR_QC = "ready_for_qc"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


@dataclass
class IntakeForm:
    agency_client_service_id: str
    client_id: str
    service: ServiceType
    plan_tier: str
    data: dict = field(default_factory=dict)  # service-specific fields
    submitted_at: Optional[datetime] = None


@dataclass
class OnboardingNotes:
    agency_client_service_id: str
    client_id: str
    call_held_at: Optional[datetime]
    notes: str
    changes_from_form: dict = field(default_factory=dict)
    additional_info: dict = field(default_factory=dict)
    finalized_by: Optional[str] = None
    finalized_at: Optional[datetime] = None


@dataclass
class TestScenarioResult:
    name: str
    result: str  # "pass" | "fail"
    detail: str = ""


@dataclass
class ServiceConfig:
    """
    agency_service_configs — new collection (see ARCHITECTURE-ADDENDUM.md).
    One record per agency_client_service_id, upserted each time this agent
    successfully implements/re-implements. This is what synkra-core's
    runtime code reads to actually run a live service — implementation_reports
    stays a per-run audit log, this is "current config."
    """
    agency_client_service_id: str
    client_id: str
    service: ServiceType
    config: dict = field(default_factory=dict)
    updated_at: Optional[datetime] = None


@dataclass
class ImplementationReport:
    agency_client_service_id: str
    client_id: str
    service: ServiceType
    status: ReportStatus
    steps_completed: list[str] = field(default_factory=list)
    test_results: list[TestScenarioResult] = field(default_factory=list)
    flags_for_human: list[str] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)  # e.g. twilio number, agent id — see README gap note
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def overall(self) -> str:
        if any(r.result == "fail" for r in self.test_results):
            return ReportStatus.NEEDS_REVIEW
        if self.flags_for_human:
            return ReportStatus.NEEDS_REVIEW
        return ReportStatus.READY_FOR_QC
