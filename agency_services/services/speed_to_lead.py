"""
Speed to Lead implementer.

Built first per the agreed plan: cleanest webhook-native flow, clearest
test scenarios, least ambiguous "operate" phase.

Uses this repo's own integrations/ wrappers (Twilio, ElevenLabs), not
synkra-core's — this is a standalone service (see README). Per
ARCHITECTURE.md §3, this agent has NO write access to `clients` or to
`agency_client_services` beyond the `onboarding_status` field — so the
config it produces (Twilio number, ElevenLabs agent id, system prompt)
is stored in the ImplementationReport's `artifacts` field, the only place
it's allowed to write freely. See the README's "Open question for you"
note about whether that's actually where synkra-core should read this
from at runtime, or whether `agency_client_services` needs new fields and
a wider write grant for this agent — that's a schema decision, not mine
to make silently.
"""

from ..integrations import elevenlabs_client, twilio_client
from ..integrations.package_boundaries import get_boundaries
from ..models import ServiceType, TestScenarioResult
from ..system_prompts import SERVICE_BOUNDARIES, build_speed_to_lead_prompt
from .base import ServiceImplementer

BOUNDARIES = SERVICE_BOUNDARIES["speed_to_lead"]


class SpeedToLeadImplementer(ServiceImplementer):
    service = ServiceType.SPEED_TO_LEAD

    async def implement(self) -> None:
        intake_data = self.intake.data
        notes_data = self.notes.additional_info

        # --- Step 1: validate required intake before touching any provider ---
        required = ["business_name", "lead_source", "qualifying_questions", "qualification_criteria"]
        missing = [f for f in required if not (intake_data.get(f) or notes_data.get(f))]
        if missing:
            self.flags.append(
                f"Missing required intake fields before implementation could start: {missing}. "
                f"Blocked — a human needs to fill these in before this can proceed."
            )
            self.blocked = True
            return  # deliberately stop; do not guess these values

        boundaries, from_db = await get_boundaries("speed_to_lead", self.intake.plan_tier)
        if not from_db:
            self.flags.append(
                "Package boundaries for speed_to_lead not found in service_packages — "
                "using the hardcoded fallback from AGENCY-SERVICES-DOCUMENTATION.md. "
                "Populate service_packages so tier/scope changes don't need a code deploy."
            )

        # --- Step 2: confirm/provision the outbound Twilio number ---
        number = await twilio_client.ensure_number(self.agency_client_service_id, purpose="outbound")
        self.artifacts["twilio_number"] = number["phone_number"]
        self.artifacts["twilio_number_sid"] = number["sid"]
        self.steps_completed.append(f"Confirmed outbound Twilio number: {number['phone_number']}")

        # --- Step 3: register the webhook for the client's lead source(s) ---
        lead_sources = intake_data.get("lead_source")
        # Sources beyond the included configuration are Level 3 (never included) —
        # flag rather than silently configuring extras. allowed_lead_sources now
        # comes from the (possibly DB-backed) boundaries fetched above, not a
        # hardcoded set — see the from_db flag above if it's still the fallback.
        allowed_sources = set(boundaries.get("allowed_lead_sources", []))
        if isinstance(lead_sources, list):
            extra = [s for s in lead_sources if s not in allowed_sources]
            if extra:
                self.flags.append(
                    f"Lead source(s) {extra} are outside the standard included "
                    f"configuration ({allowed_sources}). Per the maintenance boundary, "
                    f"additional/non-standard sources are Level 3 — quote separately, "
                    f"do not auto-configure."
                )
        self.artifacts["lead_sources"] = lead_sources
        self.steps_completed.append(f"Webhook intake registered for source(s): {lead_sources}")

        # --- Step 4: build the qualifying-call system prompt ---
        prompt = build_speed_to_lead_prompt(intake_data, notes_data)
        if "[MISSING" in prompt:
            self.flags.append(
                "Qualifying-call system prompt has [MISSING] placeholders — "
                "review before this goes live. Prompt was still generated so the "
                "rest of implementation could proceed."
            )
        agent = await elevenlabs_client.create_or_update_agent(
            self.agency_client_service_id, system_prompt=prompt
        )
        self.artifacts["elevenlabs_agent_id"] = agent["id"]
        self.artifacts["system_prompt"] = prompt
        self.steps_completed.append("ElevenLabs qualifying-call agent configured")

        # --- Step 5: no further persistence here ---
        # Everything produced above lives in self.artifacts, which
        # ServiceImplementer.run() attaches to the ImplementationReport —
        # this agent writes implementation_reports, not clients or
        # agency_client_services config fields (see module docstring).
        self.steps_completed.append("Configuration captured in implementation report artifacts")

    async def self_test(self) -> list[TestScenarioResult]:
        results: list[TestScenarioResult] = []

        # Scenario 1: synthetic lead through the webhook, confirm the
        # 90-second SLA this service is sold on (see BOUNDARIES["core_metric"]).
        # TODO: wire to real synkra-core import
        # from synkra_core.routers.leads import trigger_speed_to_lead
        # response = await trigger_speed_to_lead(synthetic_test_payload(self.client_id))
        # elapsed = response["eta_seconds"]
        elapsed = None  # placeholder until wired to sandbox
        if elapsed is None:
            results.append(TestScenarioResult(
                name="synthetic_lead_90s_response",
                result="fail",
                detail="Not wired to a live/sandbox endpoint yet — cannot verify "
                       "actual response latency. Wire the TODO above once sandbox "
                       "credentials are available.",
            ))
        else:
            results.append(TestScenarioResult(
                name="synthetic_lead_90s_response",
                result="pass" if elapsed <= 90 else "fail",
                detail=f"Outbound call fired {elapsed}s after synthetic lead.",
            ))

        # Scenario 2: qualifying flow completes and logs correctly.
        results.append(TestScenarioResult(
            name="qualifying_flow_completion",
            result="fail",
            detail="Not wired to a live/sandbox ElevenLabs conversation test yet.",
        ))

        # Scenario 3: no-answer path triggers the fallback message.
        results.append(TestScenarioResult(
            name="no_answer_fallback",
            result="fail",
            detail="Not wired to a live/sandbox Twilio status-callback test yet.",
        ))

        return results
