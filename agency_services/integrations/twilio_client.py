"""
Thin Twilio wrapper for this repo, independent of synkra-core. Uses the
`twilio` SDK directly. Every call checks `settings.environment` so a
sandbox run can never fire against a real client's production number.
"""

from ..config import settings


def _client():
    from twilio.rest import Client  # lazy import — keeps this module importable without twilio installed
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


async def ensure_number(agency_client_service_id: str, purpose: str) -> dict:
    """
    Confirms/provisions an SA number for the client, for the given
    purpose (`"inbound"` for Voice Agent, `"outbound"` for Speed to
    Lead). In `sandbox` environment this should use Twilio's trial-account
    verified-number flow (see the sandbox setup steps in the spec doc) —
    never a real purchase against production account funds.
    """
    if purpose not in ("inbound", "outbound"):
        raise ValueError(f"purpose must be 'inbound' or 'outbound', got {purpose!r}")

    if settings.environment == "sandbox":
        # Trial numbers are already provisioned per-account, not per-client —
        # this just confirms the sandbox number is reachable.
        return {"phone_number": settings.twilio_sandbox_number, "sid": "SANDBOX"}

    twilio = _client()
    numbers = twilio.available_phone_numbers("ZA").local.list(area_code="87", limit=5)
    if not numbers:
        raise RuntimeError(f"No available ZA numbers found for service {agency_client_service_id}")

    create_kwargs = {"phone_number": numbers[0].phone_number}
    if purpose == "inbound":
        # Inbound numbers need the voice webhook wired so a real call
        # actually reaches this service's /voice/incoming handler —
        # outbound-only numbers don't need this, calls are placed via API.
        create_kwargs.update({
            "voice_url": f"{settings.public_base_url}/voice/incoming",
            "voice_method": "POST",
            "status_callback": f"{settings.public_base_url}/voice/status",
            "status_callback_method": "POST",
        })
    purchased = twilio.incoming_phone_numbers.create(**create_kwargs)
    return {"phone_number": purchased.phone_number, "sid": purchased.sid}
