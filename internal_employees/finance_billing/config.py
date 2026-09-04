"""
Settings for the Finance & Billing internal employee.

Targets the AGENCY PocketBase instance (same one agency_services/ uses —
zoho_contact_id and the quotation->invoice pipeline live there per
ARCHITECTURE.md), NOT synkra-os's instance. Separate credentials from
both other employees, per the same "every automated actor gets its own
scoped account" principle already established.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    pocketbase_url: str = os.environ.get("POCKETBASE_URL", "")
    pocketbase_service_token: str = os.environ.get("POCKETBASE_SERVICE_TOKEN", "")
    # ^ Scoped, non-superuser — see README for the exact collection access
    # this employee actually needs, which is deliberately narrow.

    zoho_client_id: str = os.environ.get("ZOHO_CLIENT_ID", "")
    zoho_client_secret: str = os.environ.get("ZOHO_CLIENT_SECRET", "")
    zoho_refresh_token: str = os.environ.get("ZOHO_REFRESH_TOKEN", "")
    zoho_organization_id: str = os.environ.get("ZOHO_ORGANIZATION_ID", "")
    # Zoho's API is region-specific (.com / .eu / .in / .com.au / .jp) —
    # never hardcode one. Confirm which data center your Zoho Books
    # organization is actually on before deploying.
    zoho_accounts_base_url: str = os.environ.get("ZOHO_ACCOUNTS_BASE_URL", "https://accounts.zoho.com")
    zoho_books_base_url: str = os.environ.get("ZOHO_BOOKS_BASE_URL", "https://www.zohoapis.com/books/v3")

    poll_interval_seconds: int = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
    environment: str = os.environ.get("ENVIRONMENT", "sandbox")  # "sandbox" | "production"


settings = Settings()
