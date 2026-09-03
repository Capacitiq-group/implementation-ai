"""
Thin client for Synkra OS's PocketBase instance. Two distinct auth modes,
matching ai_jobs.pb.js exactly:

1. Employee session (via AI_EMPLOYEE_LOGIN_EMAIL/PASSWORD) — used for
   everything a normal employee session can do: reading collections
   subject to their listRule/viewRule, POST /api/ai-jobs/submit
   (requires ai.view), POST /api/email/send (requires email.manage).
2. The static AI_WORKER_API_KEY bearer token — used ONLY for
   POST /api/ai-jobs/:id/result. Never sent alongside the employee
   session; that route explicitly rejects employee-session auth (see
   requireWorkerAuth in ai_jobs.pb.js).

Lazy httpx import, same reasoning as the Implementation Employee package:
keeps this module importable and its logic testable in environments
without httpx installed (this container included — confirmed no PyPI
access here).
"""

from ..config import settings


class SynkraOSClient:
    def __init__(self) -> None:
        self.base_url = settings.synkra_os_base_url.rstrip("/")
        self._employee_token: str | None = None

    async def _authenticate(self) -> str:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/collections/users/auth-with-password",
                json={
                    "identity": settings.ai_employee_login_email,
                    "password": settings.ai_employee_login_password,
                },
            )
            resp.raise_for_status()
            self._employee_token = resp.json()["token"]
            return self._employee_token

    async def _employee_headers(self) -> dict:
        if not self._employee_token:
            await self._authenticate()
        return {"Authorization": self._employee_token, "Content-Type": "application/json"}

    async def list_records(self, collection: str, filter_expr: str = "", per_page: int = 100, sort: str = "") -> list[dict]:
        import httpx
        headers = await self._employee_headers()
        async with httpx.AsyncClient() as client:
            params = {"perPage": per_page}
            if filter_expr:
                params["filter"] = filter_expr
            if sort:
                params["sort"] = sort
            resp = await client.get(
                f"{self.base_url}/api/collections/{collection}/records",
                params=params, headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("items", [])

    async def get_record(self, collection: str, record_id: str) -> dict:
        import httpx
        headers = await self._employee_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/collections/{collection}/records/{record_id}",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_record(self, collection: str, data: dict) -> dict:
        import httpx
        headers = await self._employee_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/collections/{collection}/records",
                json=data, headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def submit_ai_job(self, task: str, action: str, input_reference: str = "") -> dict:
        """POST /api/ai-jobs/submit — requires ai.view on the employee session."""
        import httpx
        headers = await self._employee_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/ai-jobs/submit",
                json={
                    "ai_employee_id": settings.ai_employee_id,
                    "task": task,
                    "action": action,
                    "input_reference": input_reference,
                },
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def report_job_result(self, job_id: str, status: str, result: dict | None = None, error: str = "", cost_cents: int | None = None) -> dict:
        """POST /api/ai-jobs/:id/result — worker bearer token, NOT the employee session."""
        import httpx
        body = {"status": status}
        if result is not None:
            body["result"] = result
        if error:
            body["error"] = error
        if cost_cents is not None:
            body["cost_cents"] = cost_cents
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/ai-jobs/{job_id}/result",
                json=body,
                headers={"Authorization": f"Bearer {settings.ai_worker_api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_email(self, to: str, subject: str, html: str, related_customer_id: str = "") -> dict:
        """POST /api/email/send — requires email.manage on the employee session."""
        import httpx
        headers = await self._employee_headers()
        body = {"to": to, "subject": subject, "html": html}
        if related_customer_id:
            body["related_customer_id"] = related_customer_id
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/api/email/send", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()


synkra_os = SynkraOSClient()
