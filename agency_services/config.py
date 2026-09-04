"""
Settings, read from environment variables — matches the table in
portal-integration-brief.md §9 exactly. Keep these two in sync; if you
add a var here, add it to that table too, and vice versa.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    pocketbase_url: str = os.environ.get("POCKETBASE_URL", "")
    pocketbase_service_token: str = os.environ.get("POCKETBASE_SERVICE_TOKEN", "")
    # ^ Per ARCHITECTURE.md §5: this must be a scoped, non-superuser
    # service-account auth token (email/password login token for a
    # dedicated PocketBase user with collection rules matching §3's CRUD
    # table) — NOT a superuser admin token. Blanket superuser access is
    # explicitly what that doc warns against for this agent specifically.
    twilio_account_sid: str = os.environ.get("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.environ.get("TWILIO_AUTH_TOKEN", "")
    twilio_sandbox_number: str = os.environ.get("TWILIO_SANDBOX_NUMBER", "")
    elevenlabs_api_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
    deepgram_api_key: str = os.environ.get("DEEPGRAM_API_KEY", "")
    resend_api_key: str = os.environ.get("RESEND_API_KEY", "")
    kimi_api_key: str = os.environ.get("KIMI_API_KEY", "")
    environment: str = os.environ.get("ENVIRONMENT", "sandbox")  # "sandbox" | "production"
    admin_panel_internal_api_key: str = os.environ.get("ADMIN_PANEL_INTERNAL_API_KEY", "")
    public_base_url: str = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")

    def __post_init__(self):
        if self.environment not in ("sandbox", "production"):
            raise ValueError(f"ENVIRONMENT must be 'sandbox' or 'production', got {self.environment!r}")


settings = Settings()
