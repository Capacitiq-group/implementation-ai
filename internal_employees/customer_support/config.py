"""
Settings for the Customer Support AI Employee worker, read from
environment variables.
"""

from dataclasses import dataclass

from .._framework.env import env_int, env_str


@dataclass(frozen=True)
class Settings:
    synkra_os_base_url: str = env_str("SYNKRA_OS_BASE_URL", "")
    # This worker's own employee login (created by
    # scripts/bootstrap_ai_customer_support_employee.sh) — used for
    # everything except job-result reporting: reading tickets/customers/
    # knowledge base, sending email, submitting new jobs.
    ai_employee_login_email: str = env_str("AI_EMPLOYEE_LOGIN_EMAIL", "")
    ai_employee_login_password: str = env_str("AI_EMPLOYEE_LOGIN_PASSWORD", "")
    # The ai_employees collection record id for this worker instance —
    # printed by the bootstrap script. Used to filter ai_jobs to only
    # this worker's own queue.
    ai_employee_id: str = env_str("AI_EMPLOYEE_ID", "")
    # Separate static bearer token, ONLY for POST /api/ai-jobs/:id/result —
    # per ai_jobs.pb.js, this route deliberately does not accept an
    # employee session, since the worker reporting a result is a service
    # action, not something an employee session should be able to forge.
    ai_worker_api_key: str = env_str("AI_WORKER_API_KEY", "")
    # Ollama (self-hosted) is what this worker drafts replies with — NOT
    # Kimi, which is used elsewhere in the stack for OCR specifically and
    # has no business being wired into this module. Ollama exposes an
    # OpenAI-compatible endpoint at /v1/chat/completions (confirmed
    # current as of wiring this — no API key required unless you've put
    # an auth proxy in front of the self-hosted instance, hence the
    # empty-string default rather than a required var).
    ollama_base_url: str = env_str("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = env_str("OLLAMA_MODEL", "")  # no safe default — must be a model you've actually pulled
    ollama_api_key: str = env_str("OLLAMA_API_KEY", "")  # only needed if fronted by an auth proxy
    poll_interval_seconds: int = env_int("POLL_INTERVAL_SECONDS", 30)
    environment: str = env_str("ENVIRONMENT", "sandbox")  # "sandbox" | "production"


settings = Settings()
