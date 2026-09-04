"""
Base contract every per-service implementer follows. Keeps the shared
implement -> self_test -> report lifecycle in one place so adding a new
service means implementing three methods, not reinventing the loop.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from ..models import (
    ImplementationReport,
    IntakeForm,
    OnboardingNotes,
    ReportStatus,
    TestScenarioResult,
)


class ServiceImplementer(ABC):
    """
    Subclass per service. `implement()` does the real provisioning/config
    work and must be idempotent — safe to re-run if a prior attempt was
    partial (e.g. Twilio number bought but ElevenLabs agent creation
    failed). `self_test()` runs after a successful implement and must
    return TestScenarioResult objects, not just booleans, so the report
    is legible to a human doing QC.
    """

    service: str  # set by subclass, must match ServiceType value

    def __init__(self, agency_client_service_id: str, intake: IntakeForm, notes: OnboardingNotes):
        self.agency_client_service_id = agency_client_service_id
        self.client_id = intake.client_id
        self.intake = intake
        self.notes = notes
        self.steps_completed: list[str] = []
        self.flags: list[str] = []
        self.artifacts: dict = {}  # config produced during implement() — see README gap note
        self.blocked = False  # set True in implement() to halt before self_test runs

    @abstractmethod
    async def implement(self) -> None:
        """Do the actual provisioning/configuration. Append to
        self.steps_completed as each step succeeds. Append to self.flags
        for anything blocked, missing, or out of scope (Level 3 work) —
        never silently skip."""
        raise NotImplementedError

    @abstractmethod
    async def self_test(self) -> list[TestScenarioResult]:
        """Run service-specific test scenarios against what implement()
        just built. Must not touch real client-facing channels with
        anything a real customer could see (no test calls to real
        numbers other than sandboxed ones, no test sends to real
        contacts)."""
        raise NotImplementedError

    async def run(self) -> ImplementationReport:
        report = ImplementationReport(
            agency_client_service_id=self.agency_client_service_id,
            client_id=self.client_id,
            service=self.service,
            status=ReportStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )
        try:
            await self.implement()
        except Exception as exc:  # noqa: BLE001 — surfaced to human, not swallowed
            self.flags.append(f"implement() raised: {exc!r}")
            report.steps_completed = self.steps_completed
            report.flags_for_human = self.flags
            report.artifacts = self.artifacts
            report.status = ReportStatus.BLOCKED
            report.completed_at = datetime.now(timezone.utc)
            return report

        if self.blocked:
            report.steps_completed = self.steps_completed
            report.flags_for_human = self.flags
            report.artifacts = self.artifacts
            report.status = ReportStatus.BLOCKED
            report.completed_at = datetime.now(timezone.utc)
            return report

        test_results = await self.self_test()

        report.steps_completed = self.steps_completed
        report.flags_for_human = self.flags
        report.artifacts = self.artifacts
        report.test_results = test_results
        report.status = report.overall()
        report.completed_at = datetime.now(timezone.utc)
        return report
