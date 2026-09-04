"""
Builds Zoho line items from an agency_client_services record. Pricing
comes from the record itself — `setup_price`/`monthly_price` are locked
at purchase time per ARCHITECTURE.md, so they're the actual agreed deal
for this specific client, not necessarily identical to service_packages'
generic tier default (a client could have a negotiated price).
service_packages is used only for descriptive content (what's included),
never for the price itself — never override what was actually agreed.
"""

SERVICE_DISPLAY_NAMES = {
    "voice_agent": "AI Voice Agent",
    "speed_to_lead": "Speed to Lead",
    "lead_reactivation": "Lead Reactivation",
    "custom_agentic_employee": "Custom Agentic AI Employee",
}


def build_quote_line_items(service_record: dict, package_boundaries: dict | None = None) -> list[dict]:
    """
    Pure function — no I/O. Returns Zoho-shaped line_items, or raises
    ValueError if the record is missing what's needed to quote honestly
    (never fabricate a price). Callers must catch this and treat it as a
    blocker, not proceed with a guessed amount.
    """
    service_slug = service_record.get("service_slug")
    tier = service_record.get("tier")
    setup_price = service_record.get("setup_price")
    monthly_price = service_record.get("monthly_price")

    if not service_slug or not tier:
        raise ValueError("service_record is missing service_slug or tier — cannot build a quote.")
    if setup_price is None and monthly_price is None:
        raise ValueError(
            f"service_record for {service_slug}/{tier} has no setup_price or "
            f"monthly_price set — cannot quote an unpriced service. This needs "
            f"a human to set pricing on the record before a quote can be drafted."
        )

    display_name = SERVICE_DISPLAY_NAMES.get(service_slug, service_slug)
    tier_label = tier.capitalize()

    included = []
    if package_boundaries:
        included = package_boundaries.get("included_every_tier", [])
    description = "Includes: " + "; ".join(included) if included else ""

    line_items = []
    if setup_price is not None and float(setup_price) > 0:
        line_items.append({
            "name": f"{display_name} — {tier_label} — Setup",
            "description": description,
            "rate": float(setup_price),
            "quantity": 1,
        })
    if monthly_price is not None and float(monthly_price) > 0:
        line_items.append({
            "name": f"{display_name} — {tier_label} — Monthly",
            "description": description,
            "rate": float(monthly_price),
            "quantity": 1,
        })

    if not line_items:
        raise ValueError(
            f"service_record for {service_slug}/{tier} has setup_price and "
            f"monthly_price both set to 0 or less — nothing to quote."
        )

    return line_items
