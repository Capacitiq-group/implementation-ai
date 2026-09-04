"""
Settings for the Finance & Billing internal employee.

Targets the AGENCY PocketBase instance (same one agency_services/ uses —
zoho_contact_id and the quotation->invoice pipeline live there per
ARCHITECTURE.md), NOT synkra-os's instance. Separate credentials from
both other employees, per the same "every automated actor gets its own
scoped account" principle already established.
"""

from dataclasses import dataclass

from .._framework.env import env_int, env_str


@dataclass(frozen=True)
class Settings:
    pocketbase_url: str = env_str("POCKETBASE_URL", "")
    pocketbase_service_token: str = env_str("POCKETBASE_SERVICE_TOKEN", "")
    # ^ Scoped, non-superuser — see README for the exact collection access
    # this employee actually needs, which is deliberately narrow.

    zoho_client_id: str = env_str("ZOHO_CLIENT_ID", "")
    zoho_client_secret: str = env_str("ZOHO_CLIENT_SECRET", "")
    zoho_refresh_token: str = env_str("ZOHO_REFRESH_TOKEN", "")
    zoho_organization_id: str = env_str("ZOHO_ORGANIZATION_ID", "")
    # Zoho's API is region-specific (.com / .eu / .in / .com.au / .jp) —
    # never hardcode one. Confirm which data center your Zoho Books
    # organization is actually on before deploying.
    zoho_accounts_base_url: str = env_str("ZOHO_ACCOUNTS_BASE_URL", "https://accounts.zoho.com")
    zoho_books_base_url: str = env_str("ZOHO_BOOKS_BASE_URL", "https://www.zohoapis.com/books/v3")

    poll_interval_seconds: int = env_int("POLL_INTERVAL_SECONDS", 300)
    environment: str = env_str("ENVIRONMENT", "sandbox")  # "sandbox" | "production"


settings = Settings()
