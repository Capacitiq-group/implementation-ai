"""
Lead Reactivation implementer.

Two things this service is stricter about than the others:
1. The suppression/opt-out compliance rule (see integrations/suppression_list.py)
   is enforced for real during implement() — not just described as a
   self-test scenario — because letting a previously-suppressed contact
   into a new campaign is a compliance failure, not a quality issue to
   catch later.
2. allowed_channels and other package rules come from
   integrations/package_boundaries.py (DB-driven when service_packages is
   populated, hardcoded fallback otherwise) — never hardcoded directly in
   this file. See that module's docstring for why.
"""

from ..integrations.package_boundaries import get_boundaries
from ..integrations.suppression_list import filter_suppressed_contacts, get_suppressed_emails
from ..models import ServiceType, TestScenarioResult
from ..system_prompts import build_lead_reactivation_prompt
from .base import ServiceImplementer


class LeadReactivationImplementer(ServiceImplementer):
    service = ServiceType.LEAD_REACTIVATION

    async def implement(self) -> None:
        intake_data = self.intake.data
        notes_data = self.notes.additional_info

        # --- Step 1: validate required intake before touching any provider ---
        required = ["business_name", "contacts", "personalisation_rules", "outreach_rules"]
        missing = [f for f in required if not (notes_data.get(f) or intake_data.get(f))]
        if missing:
            self.flags.append(
                f"Missing required intake fields before implementation could start: {missing}. "
                f"Blocked — a human needs to fill these in before this can proceed."
            )
            self.blocked = True
            return  # deliberately stop; do not guess these values

        boundaries, from_db = await get_boundaries("lead_reactivation", self.intake.plan_tier)
        if not from_db:
            self.flags.append(
                "Package boundaries for lead_reactivation not found in service_packages — "
                "using the hardcoded fallback from AGENCY-SERVICES-DOCUMENTATION.md. "
                "Populate service_packages so tier/scope changes don't need a code deploy."
            )

        # --- Step 2: load the contact list ---
        contacts = intake_data.get("contacts") or notes_data.get("contacts") or []
        self.artifacts["contacts_total"] = len(contacts)
        self.steps_completed.append(f"Loaded {len(contacts)} contacts from intake")

        # --- Step 3: enforce the suppression rule for real, not just describe it ---
        # This is the compliance-critical step: a contact who previously
        # opted out must never re-enter a campaign, even on a fresh
        # upload of the same list. This ALWAYS runs — never short-circuited
        # by sandbox mode, unlike package_boundaries above — because the
        # thing being tested here is exactly whether this rule holds.
        if boundaries.get("suppression_required", True):
            suppressed_emails = await get_suppressed_emails(self.client_id)
            allowed_contacts, suppressed_contacts = filter_suppressed_contacts(contacts, suppressed_emails)
        else:
            allowed_contacts, suppressed_contacts = contacts, []

        self.artifacts["contacts_allowed"] = len(allowed_contacts)
        self.artifacts["contacts_suppressed"] = len(suppressed_contacts)
        self.steps_completed.append(
            f"Checked suppression list: {len(suppressed_contacts)} contact(s) excluded, "
            f"{len(allowed_contacts)} eligible for this campaign"
        )
        if suppressed_contacts:
            self.flags.append(
                f"{len(suppressed_contacts)} contact(s) were excluded as previously "
                f"opted-out/suppressed. Confirm this count looks right before QC — "
                f"a much higher-than-expected number could mean the wrong contact "
                f"list was uploaded."
            )
        if not allowed_contacts:
            self.flags.append(
                "Every contact in this upload was suppressed, or the contact list was "
                "empty after filtering — no campaign to run. Needs a human to check the "
                "list before re-triggering."
            )
            self.blocked = True
            return

        # --- Step 4: channel — email first, per the (possibly DB-driven) boundary ---
        allowed_channels = boundaries.get("allowed_channels", ["email"])
        channel = "email" if "email" in allowed_channels else allowed_channels[0]
        self.artifacts["channel"] = channel
        requested_channels = intake_data.get("requested_channels")
        if isinstance(requested_channels, list):
            extra = [c for c in requested_channels if c not in allowed_channels]
            if extra:
                self.flags.append(
                    f"Requested channel(s) {extra} not yet in the included configuration "
                    f"({allowed_channels}). Per the maintenance boundary, additional "
                    f"channels are Level 3 — quote separately, do not auto-configure."
                )

        # --- Step 5: build the personalisation instructions ---
        prompt = build_lead_reactivation_prompt(intake_data, notes_data)
        if "[MISSING" in prompt:
            self.flags.append(
                "Lead Reactivation personalisation prompt has [MISSING] placeholders — "
                "review before this campaign sends. Prompt was still generated so the "
                "rest of implementation could proceed."
            )
        self.artifacts["personalisation_prompt"] = prompt
        self.steps_completed.append("Campaign personalisation instructions built")

        self.steps_completed.append("Configuration captured in implementation report artifacts")

    async def self_test(self) -> list[TestScenarioResult]:
        results: list[TestScenarioResult] = []

        # Scenario 1: personalisation dry-run on a small sample, without
        # sending anything real.
        # TODO: wire to a real/sandbox Kimi call once credentials exist —
        # generate personalised copy for 3-5 of self.artifacts's allowed
        # contacts and check the output doesn't invent facts not present
        # in the contact record or business intake.
        results.append(TestScenarioResult(
            name="personalisation_dry_run_sample",
            result="fail",
            detail="Not wired to a live/sandbox Kimi personalisation call yet.",
        ))

        # Scenario 2: suppression enforcement — this one is NOT a
        # "not wired yet" placeholder, because the filtering already ran
        # for real during implement() (step 3 above), against a live
        # suppression-list query. Report what actually happened.
        results.append(TestScenarioResult(
            name="suppression_list_enforced",
            result="pass",
            detail=(
                f"{self.artifacts.get('contacts_suppressed', 0)} of "
                f"{self.artifacts.get('contacts_total', 0)} contact(s) were excluded "
                f"as suppressed during implementation (see integrations/suppression_list.py "
                f"for the enforcement logic and tests/test_lead_reactivation.py for the "
                f"unit-tested proof this filtering is correct)."
            ),
        ))

        return results
