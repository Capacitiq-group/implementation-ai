"""
Reads service/tier package boundaries (what's included, what's not,
allowed channels/sources, compliance rules) from a new PocketBase
collection — `service_packages` — at runtime, instead of relying solely
on the hardcoded SERVICE_BOUNDARIES dict in system_prompts.py.

Why this exists: SERVICE_BOUNDARIES was a one-time transcription from
AGENCY-SERVICES-DOCUMENTATION.md into Python. That's fine as a starting
point and a guaranteed fallback, but it means every future pricing/scope
change needs a code change and redeploy to take effect — backwards for
data the business side should be able to edit directly. This makes the
database the source of truth once populated, and only falls back to the
hardcoded transcription when it isn't — see ARCHITECTURE-ADDENDUM for the
new collection's schema and CRUD table.

Sandbox note: in `ENVIRONMENT=sandbox`, this always uses the hardcoded
fallback without touching the network at all — `service_packages` won't
be populated yet during early testing, and this data is genuinely
optional (there's always a safe fallback), unlike the suppression list in
suppression_list.py, which is compliance-critical and always queried for
real regardless of environment.
"""

from ..config import settings
from ..system_prompts import SERVICE_BOUNDARIES
from .pocketbase_client import pocketbase


async def get_boundaries(service: str, tier: str) -> tuple[dict, bool]:
    """
    Returns (boundaries, from_database). Callers should flag in their
    report when from_database is False, so it's visible that a
    service/tier's boundaries are still running off the hardcoded
    fallback rather than an admin-editable record — that's a signal to
    populate service_packages, not a silent, permanent state.
    """
    fallback = SERVICE_BOUNDARIES.get(service, {})

    if settings.environment == "sandbox":
        return fallback, False

    try:
        record = await pocketbase.get_record(
            "service_packages", f"service='{service}' && tier='{tier}'"
        )
    except Exception:
        # DB unreachable or collection not created yet — never let this
        # block an implementation run; fall back and flag it instead.
        return fallback, False

    if record and record.get("boundaries"):
        return record["boundaries"], True
    return fallback, False
