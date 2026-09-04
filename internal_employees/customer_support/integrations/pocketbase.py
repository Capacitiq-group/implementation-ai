"""
Client for Synkra OS's PocketBase instance. The plain record CRUD comes
from _framework/pocketbase.py; what's specific to this employee — and
kept here — is the two distinct auth modes, matching ai_jobs.pb.js:

1. Employee session (via AI_EMPLOYEE_LOGIN_EMAIL/PASSWORD) — used for
   everything a normal employee session can do: reading collections
   subject to their listRule/viewRule, POST /api/ai-jobs/submit
   (requires ai.view), POST /api/email/send (requires email.manage).
2. The static AI_WORKER_API_KEY bearer token — used ONLY for
   POST /api/ai-jobs/:id/result. Never sent alongside the employee
   session; that route explicitly rejects employee-session auth (see
   requireWorkerAuth in ai_jobs.pb.js).
"""

from ..._framework.http import request_json
from ..._framework.pocketbase import BasePocketBaseClient
from ..config import settings


class SynkraOSClient(BasePocketBaseClient):
    def __init__(self) -> None:
        super().__init__(settings.synkra_os_base_url)
        self._employee_token: str | None = None

    async def _authenticate(self) -> str:
        payload = await request_json(
            "POST",
            self._url("/api/collections/users/auth-with-password"),
            json={
                "identity": settings.ai_employee_login_email,
                "password": settings.ai_employee_login_password,
            },
        )
        self._employee_token = payload["token"]
        return self._employee_token

    async def headers(self) -> dict:
        if not self._employee_token:
            await self._authenticate()
        return {"Authorization": self._employee_token, "Content-Type": "application/json"}

    # Kept as the historical name used across this package.
    async def _employee_headers(self) -> dict:
        return await self.headers()

    async def get_record(self, collection: str, record_id: str) -> dict:
        return await self.get_record_by_id(collection, record_id)

    async def submit_ai_job(self, task: str, action: str, input_reference: str = "") -> dict:
        """POST /api/ai-jobs/submit — requires ai.view on the employee session."""
        return await request_json(
            "POST",
            self._url("/api/ai-jobs/submit"),
            json={
                "ai_employee_id": settings.ai_employee_id,
                "task": task,
                "action": action,
                "input_reference": input_reference,
            },
            headers=await self.headers(),
        )

    async def report_job_result(
        self,
        job_id: str,
        status: str,
        result: dict | None = None,
        error: str = "",
        cost_cents: int | None = None,
    ) -> dict:
        """POST /api/ai-jobs/:id/result — worker bearer token, NOT the employee session."""
        body: dict = {"status": status}
        if result is not None:
            body["result"] = result
        if error:
            body["error"] = error
        if cost_cents is not None:
            body["cost_cents"] = cost_cents
        return await request_json(
            "POST",
            self._url(f"/api/ai-jobs/{job_id}/result"),
            json=body,
            headers={"Authorization": f"Bearer {settings.ai_worker_api_key}"},
        )

    async def send_email(self, to: str, subject: str, html: str, related_customer_id: str = "") -> dict:
        """POST /api/email/send — requires email.manage on the employee session."""
        body = {"to": to, "subject": subject, "html": html}
        if related_customer_id:
            body["related_customer_id"] = related_customer_id
        return await request_json(
            "POST", self._url("/api/email/send"), json=body, headers=await self.headers()
        )


synkra_os = SynkraOSClient()
