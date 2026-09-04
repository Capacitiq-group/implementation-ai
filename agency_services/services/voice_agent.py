"""
Voice Agent implementer — built out following services/speed_to_lead.py's
pattern exactly: validate required intake before touching any provider
(never guess), provision via this repo's own integrations/ wrappers, flag
anything out of the tier's included scope rather than silently building
it, capture produced config in self.artifacts (persisted to
agency_service_configs by the orchestrator — see README).
"""

from ..integrations import elevenlabs_client, twilio_client
from ..models import ServiceType, TestScenarioResult
from ..system_prompts import SERVICE_BOUNDARIES, build_voice_agent_prompt
from .base import ServiceImplementer

BOUNDARIES = SERVICE_BOUNDARIES["voice_agent"]


class VoiceAgentImplementer(ServiceImplementer):
    service = ServiceType.VOICE_AGENT

    async def implement(self) -> None:
        intake_data = self.intake.data
        notes_data = self.notes.additional_info

        # --- Step 1: validate required intake before touching any provider ---
        # transfer_instructions and booking_process are deliberately NOT
        # required — their absence is meaningful (no transfer number
        # configured, no booking integration) and build_voice_agent_prompt
        # already handles that by defaulting to "take a message" behaviour
        # rather than blocking on it.
        required = [
            "business_name", "business_description",
            "services_and_prices", "operating_hours", "faqs",
        ]
        missing = [f for f in required if not (notes_data.get(f) or intake_data.get(f))]
        if missing:
            self.flags.append(
                f"Missing required intake fields before implementation could start: {missing}. "
                f"Blocked — a human needs to fill these in before this can proceed."
            )
            self.blocked = True
            return  # deliberately stop; do not guess these values

        # --- Step 2: confirm/provision the inbound Twilio number ---
        number = await twilio_client.ensure_number(self.agency_client_service_id, purpose="inbound")
        self.artifacts["twilio_number"] = number["phone_number"]
        self.artifacts["twilio_number_sid"] = number["sid"]
        self.steps_completed.append(f"Confirmed inbound Twilio number: {number['phone_number']}")

        # --- Step 3: flag anything that would require Level-3 work ---
        # A configured transfer number implies human-transfer routing —
        # standard/included. Anything asking for CRM/booking-system access
        # beyond what's explicitly provided as plain instructions is out
        # of scope per BOUNDARIES["cannot_do"].
        if intake_data.get("requires_crm_integration") or notes_data.get("requires_crm_integration"):
            self.flags.append(
                "Intake/notes indicate the client wants direct booking/CRM system "
                "access. Per the service boundary, this agent cannot access a "
                "business's own booking/CRM system without additional integration "
                "work — that's Level 3, quote separately, do not attempt to build it here."
            )

        # --- Step 4: build the client-facing system prompt ---
        prompt = build_voice_agent_prompt(intake_data, notes_data)
        if "[MISSING" in prompt:
            self.flags.append(
                "Voice Agent system prompt has [MISSING] placeholders — "
                "review before this goes live. Prompt was still generated so the "
                "rest of implementation could proceed."
            )
        agent = await elevenlabs_client.create_or_update_agent(
            self.agency_client_service_id, system_prompt=prompt
        )
        self.artifacts["elevenlabs_agent_id"] = agent["id"]
        self.artifacts["system_prompt"] = prompt
        self.steps_completed.append("ElevenLabs voice agent configured")

        self.steps_completed.append("Configuration captured in implementation report artifacts")

    async def self_test(self) -> list[TestScenarioResult]:
        results: list[TestScenarioResult] = []

        # Scenario 1: FAQ answer — caller asks something covered in the
        # intake FAQs, agent should answer from that content, not invent.
        # TODO: wire to a real/sandbox ElevenLabs test-conversation call
        # once credentials exist, and assert the response is grounded in
        # the actual faqs field rather than a plausible-sounding guess.
        results.append(TestScenarioResult(
            name="faq_answer_grounded_in_intake",
            result="fail",
            detail="Not wired to a live/sandbox ElevenLabs conversation test yet.",
        ))

        # Scenario 2: transfer trigger — caller asks for a human /
        # something outside scope, agent should follow transfer_instructions
        # (or the "take a message" fallback if none configured) rather
        # than attempting to handle it itself.
        results.append(TestScenarioResult(
            name="transfer_or_fallback_trigger",
            result="fail",
            detail="Not wired to a live/sandbox ElevenLabs conversation test yet.",
        ))

        # Scenario 3: "can't help" -> message capture — caller asks
        # something with no matching FAQ/instruction, agent should offer
        # to take name + number rather than fabricate an answer.
        results.append(TestScenarioResult(
            name="unknown_query_message_capture",
            result="fail",
            detail="Not wired to a live/sandbox ElevenLabs conversation test yet.",
        ))

        return results
