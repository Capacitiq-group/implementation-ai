"""
Thin PocketBase client for the Agency instance. Same pattern as the
other two employees' own clients — lazy httpx import so this stays
importable/testable without httpx installed, employee-scoped auth token
rather than a superuser.
"""

from ..config import settings


class AgencyPocketBaseClient:
    def __init__(self) -> None:
        self.base_url = settings.pocketbase_url.rstrip("/")
        self.token = settings.pocketbase_service_token

    def _headers(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    async def get_record(self, collection: str, filter_expr: str) -> dict | None:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/collections/{collection}/records",
                params={"filter": filter_expr, "perPage": 1},
                headers=self._headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return items[0] if items else None

    async def list_records(self, collection: str, filter_expr: str = "", per_page: int = 200, sort: str = "") -> list[dict]:
        import httpx
        async with httpx.AsyncClient() as client:
            params = {"perPage": per_page}
            if filter_expr:
                params["filter"] = filter_expr
            if sort:
                params["sort"] = sort
            resp = await client.get(
                f"{self.base_url}/api/collections/{collection}/records",
                params=params, headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("items", [])

    async def create_record(self, collection: str, data: dict) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/collections/{collection}/records",
                json=data, headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def update_record(self, collection: str, record_id: str, data: dict) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.base_url}/api/collections/{collection}/records/{record_id}",
                json=data, headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()


pocketbase = AgencyPocketBaseClient()
