"""
Base PocketBase REST client. Subclasses supply the base URL and how a
request is authenticated — that is the only part that genuinely differs
between employees (employee session vs. scoped service token).
"""

from .http import request_json


class BasePocketBaseClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = (base_url or "").rstrip("/")

    async def headers(self) -> dict:
        """Override: return the auth headers for this employee."""
        return {"Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def list_records(
        self, collection: str, filter_expr: str = "", per_page: int = 100, sort: str = ""
    ) -> list[dict]:
        params: dict = {"perPage": per_page}
        if filter_expr:
            params["filter"] = filter_expr
        if sort:
            params["sort"] = sort
        payload = await request_json(
            "GET", self._url(f"/api/collections/{collection}/records"),
            params=params, headers=await self.headers(),
        )
        return payload.get("items", [])

    async def find_first(self, collection: str, filter_expr: str) -> dict | None:
        items = await self.list_records(collection, filter_expr=filter_expr, per_page=1)
        return items[0] if items else None

    async def get_record_by_id(self, collection: str, record_id: str) -> dict:
        return await request_json(
            "GET", self._url(f"/api/collections/{collection}/records/{record_id}"),
            headers=await self.headers(),
        )

    async def create_record(self, collection: str, data: dict) -> dict:
        return await request_json(
            "POST", self._url(f"/api/collections/{collection}/records"),
            json=data, headers=await self.headers(),
        )

    async def update_record(self, collection: str, record_id: str, data: dict) -> dict:
        return await request_json(
            "PATCH", self._url(f"/api/collections/{collection}/records/{record_id}"),
            json=data, headers=await self.headers(),
        )
