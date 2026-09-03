"""
Settings for the Customer Support AI Employee worker, read from
environment variables.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    synkra_os_base_url: str = os.environ.get("SYNKRA_OS_BASE_URL", "")
    # This worker's own employee login (created by
    # scripts/bootstrap_ai_customer_support_employee.sh) — used for
    # everything except job-result reporting: reading tickets/customers/
    # knowledge base, sending email, submitting new jobs.
    ai_employee_login_email: str = os.environ.get("AI_EMPLOYEE_LOGIN_EMAIL", "")
    ai_employee_login_password: str = os.environ.get("AI_EMPLOYEE_LOGIN_PASSWORD", "")
    # The ai_employees collection record id for this worker instance —
    # printed by the bootstrap script. Used to filter ai_jobs to only
    # this worker's own queue.
    ai_employee_id: str = os.environ.get("AI_EMPLOYEE_ID", "")
    # Separate static bearer token, ONLY for POST /api/ai-jobs/:id/result —
    # per ai_jobs.pb.js, this route deliberately does not accept an
    # employee session, since the worker reporting a result is a service
    # action, not something an employee session should be able to forge.
    ai_worker_api_key: str = os.environ.get("AI_WORKER_API_KEY", "")
    kimi_api_key: str = os.environ.get("KIMI_API_KEY", "")
    poll_interval_seconds: int = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
    environment: str = os.environ.get("ENVIRONMENT", "sandbox")  # "sandbox" | "production"


settings = Settings()
