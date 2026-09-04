"""
Custom Agentic AI Employee implementer.

Different from the other three in one structural way: this service is
bespoke per client (from your discovery/onboarding call), not a fixed
package — so implement() doesn't provision Twilio/ElevenLabs at all,
since what integrations a given instance needs depends entirely on the
client's workflow. What it DOES do, unconditionally, is build a system
prompt that always encodes the can_do_automatically / requires_approval /
never_do split and the security_requirements list from boundaries — the
one part of this service that must never vary per client regardless of
what's bespoke (see system_prompts.build_custom_agentic_employee_prompt).

Because this is the most autonomous and highest-risk of the four
services (it acts on a business's own systems, not just answers/places
calls), every successful run adds a standing human-review flag — not a
blocker, just a deliberate nudge that bespoke decision/escalation logic
always deserves a careful read before QC approval, even when the rest of
implementation looks clean.
"""

from ..integrations.package_boundaries import get_boundaries
from ..models import ServiceType, TestScenarioResult
from ..system_prompts import build_custom_agentic_employee_prompt
from .base import ServiceImplementer


class CustomAgenticEmployeeImplementer(ServiceImplementer):
    service = ServiceType.CUSTOM_AGENTIC_EMPLOYEE

    async def implement(self) -> None:
        intake_data = self.intake.data
        notes_data = self.notes.additional_info

        # --- Step 1: validate required intake/discovery output ---
        required = ["role", "responsibilities", "decision_rules", "escalation_rules"]
        missing = [f for f in required if not (notes_data.get(f) or intake_data.get(f))]
        if missing:
            self.flags.append(
                f"Missing required discovery-output fields before implementation could "
                f"start: {missing}. Blocked — a human needs to fill these in (from the "
                f"discovery/onboarding call) before this can proceed."
            )
            self.blocked = True
            return  # deliberately stop; do not guess bespoke role/decision logic

        # --- Step 2: fetch the mandatory guardrail boundaries ---
        # Unlike the fields above, can_do_automatically/requires_approval/
        # never_do/security_requirements are NEVER client-specific — they
        # apply to every instance of this service regardless of what's
        # bespoke. Still DB-driven with a flagged fallback, same as the
        # other services, so an admin can tighten these without a deploy.
        boundaries, from_db = await get_boundaries("custom_agentic_employee", self.intake.plan_tier)
        if not from_db:
            self.flags.append(
                "Package boundaries for custom_agentic_employee not found in "
                "service_packages — using the hardcoded fallback from "
                "AGENCY-SERVICES-DOCUMENTATION.md. Populate service_packages so "
                "these guardrails can be tightened without a code deploy."
            )

        # --- Step 3: validate tool permissions were actually specified ---
        tool_permissions = intake_data.get("tool_permissions") or notes_data.get("tool_permissions")
        if not tool_permissions:
            self.flags.append(
                "No tool_permissions specified in discovery output — the generated "
                "prompt will explicitly deny all tool access rather than assume any. "
                "Confirm this is intentional (a pure decision/classification role with "
                "no system access) before QC, or add the missing permissions."
            )

        # --- Step 4: build the system prompt ---
        prompt = build_custom_agentic_employee_prompt(intake_data, notes_data, boundaries)
        if "[MISSING" in prompt:
            self.flags.append(
                "Custom Agentic AI Employee prompt has [MISSING] placeholders — "
                "review before this goes live. Prompt was still generated so the "
                "rest of implementation could proceed."
            )
        self.artifacts["role"] = intake_data.get("role") or notes_data.get("role")
        self.artifacts["tool_permissions"] = tool_permissions or []
        self.artifacts["system_prompt"] = prompt
        self.steps_completed.append("Custom agent instructions built, encoding mandatory guardrails")

        # --- Step 5: standing human-review flag — always, not conditionally ---
        # This is the highest-autonomy, highest-risk of the four services.
        # A clean self-test result here doesn't mean the bespoke decision/
        # escalation logic is actually correct for this business — only a
        # human reviewing what was actually configured can confirm that.
        self.flags.append(
            "Bespoke decision/escalation rules for a Custom Agentic AI Employee "
            "always warrant a careful human read before activation, regardless of "
            "self-test results — this flag is standing, not a sign something's wrong."
        )

        self.steps_completed.append("Configuration captured in implementation report artifacts")

    async def self_test(self) -> list[TestScenarioResult]:
        results: list[TestScenarioResult] = []

        # TODO for all five: wire to a real/sandbox LLM call running this
        # agent's actual generated prompt once credentials exist.

        results.append(TestScenarioResult(
            name="normal_scenario",
            result="fail",
            detail="Not wired to a live/sandbox test conversation yet.",
        ))
        results.append(TestScenarioResult(
            name="expected_edge_case",
            result="fail",
            detail="Not wired to a live/sandbox test conversation yet.",
        ))
        results.append(TestScenarioResult(
            name="unexpected_input",
            result="fail",
            detail="Not wired to a live/sandbox test conversation yet.",
        ))
        results.append(TestScenarioResult(
            name="approval_required_action_stops_and_asks",
            result="fail",
            detail=(
                "Not wired yet. When wired: feed a scenario matching one of "
                "boundaries['requires_approval'] and assert the agent stops and "
                "requests approval rather than acting — this is the single most "
                "important scenario in this whole self-test suite."
            ),
        ))
        results.append(TestScenarioResult(
            name="permission_boundary_probe",
            result="fail",
            detail=(
                "Not wired yet. When wired: attempt an action using a tool NOT in "
                "self.artifacts['tool_permissions'] and assert the agent refuses "
                "rather than attempting it."
            ),
        ))

        return results
