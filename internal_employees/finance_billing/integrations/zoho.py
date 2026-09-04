"""
Zoho Books integration. Confirmed against Zoho's current docs while
building this (not assumed): estimates use the field names customer_id,
date, expiry_date, reference_number, line_items (each with name,
description, rate, quantity); auth is `Authorization: Zoho-oauthtoken
{access_token}`; organization_id is a required query param on every
call; OAuth token refresh is the standard grant_type=refresh_token flow
against the Zoho Accounts API, separate from the Books API itself.

**This module never sets `send: true` on anything it creates.** A quote
or invoice always lands in Zoho as a draft. Actually emailing it to a
customer is a human action, taken through Zoho's own UI or a
deliberately separate, explicitly-approved step — not something this
employee decides on its own. Same principle as every other
money-adjacent guardrail in this codebase: draft and flag, never commit.

No PocketBase write-back for the contact_id mapping — rather than
needing a new write grant on `clients.zoho_contact_id` (which would mean
widening this employee's PocketBase permissions beyond its own
collection), contact lookup is by email against Zoho itself, treating
Zoho as the source of truth for that mapping. Slightly more API calls,
zero new permission surface.
"""

from ..config import settings


class ZohoTokenCache:
    """Tiny in-process cache so we're not refreshing the access token on
    every single call — Zoho access tokens are short-lived (~1hr) but a
    fresh one per request is wasteful and rate-limit-unfriendly."""
    def __init__(self) -> None:
        self._access_token: str | None = None

    async def get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.zoho_accounts_base_url}/oauth/v2/token",
                params={
                    "grant_type": "refresh_token",
                    "client_id": settings.zoho_client_id,
                    "client_secret": settings.zoho_client_secret,
                    "refresh_token": settings.zoho_refresh_token,
                },
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            return self._access_token

    def invalidate(self) -> None:
        self._access_token = None


_token_cache = ZohoTokenCache()


async def _headers() -> dict:
    token = await _token_cache.get_access_token()
    return {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}


async def find_or_create_contact(name: str, email: str) -> str:
    """Returns a Zoho contact_id, searching by email first. Creates a new
    contact only if none matches — never creates a duplicate for a repeat
    client."""
    import httpx
    async with httpx.AsyncClient() as client:
        headers = await _headers()
        search_resp = await client.get(
            f"{settings.zoho_books_base_url}/contacts",
            params={"organization_id": settings.zoho_organization_id, "email": email},
            headers=headers,
        )
        search_resp.raise_for_status()
        matches = search_resp.json().get("contacts", [])
        if matches:
            return matches[0]["contact_id"]

        create_resp = await client.post(
            f"{settings.zoho_books_base_url}/contacts",
            params={"organization_id": settings.zoho_organization_id},
            headers=headers,
            json={"contact_name": name, "email": email},
        )
        create_resp.raise_for_status()
        return create_resp.json()["contact"]["contact_id"]


async def create_draft_estimate(customer_id: str, reference_number: str, expiry_date: str, line_items: list[dict]) -> dict:
    """Creates a Zoho estimate (their term for a quote) as a draft.
    Deliberately does not pass `send`, which defaults to not sending —
    see module docstring."""
    import httpx
    async with httpx.AsyncClient() as client:
        headers = await _headers()
        resp = await client.post(
            f"{settings.zoho_books_base_url}/estimates",
            params={"organization_id": settings.zoho_organization_id},
            headers=headers,
            json={
                "customer_id": customer_id,
                "reference_number": reference_number,
                "expiry_date": expiry_date,
                "line_items": line_items,
            },
        )
        resp.raise_for_status()
        return resp.json()["estimate"]


async def get_estimate_status(estimate_id: str) -> str:
    """Reads an estimate's current status (draft/sent/accepted/declined/
    expired) — used for the payment/status-monitoring loop, not for
    drafting."""
    import httpx
    async with httpx.AsyncClient() as client:
        headers = await _headers()
        resp = await client.get(
            f"{settings.zoho_books_base_url}/estimates/{estimate_id}",
            params={"organization_id": settings.zoho_organization_id},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["estimate"]["status"]


async def get_invoice_status(invoice_id: str) -> str:
    """Reads an invoice's current status (draft/sent/paid/overdue/void)."""
    import httpx
    async with httpx.AsyncClient() as client:
        headers = await _headers()
        resp = await client.get(
            f"{settings.zoho_books_base_url}/invoices/{invoice_id}",
            params={"organization_id": settings.zoho_organization_id},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["invoice"]["status"]
