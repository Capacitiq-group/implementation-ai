"""
Thin PocketBase client for this repo. Deliberately not importing
synkra-core's PocketBase helpers — this service is a standalone repo/deploy
(per your call to decouple it from synkra-core) that talks to the same
Agency PocketBase instance purely over its HTTP API, using its own
service-account token.

Uses plain httpx rather than a PocketBase SDK to keep the dependency list
small — swap for the official SDK if you'd rather standardize on it.
"""

from ..config import settings


class PocketBaseClient:
    def __init__(self) -> None:
        self.base_url = settings.pocketbase_url.rstrip("/")
        self.token = settings.pocketbase_service_token

    def _headers(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    async def get_record(self, collection: str, filter_expr: str) -> dict | None:
        import httpx  # lazy import — keeps this module importable in envs without httpx installed
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/collections/{collection}/records",
                params={"filter": filter_expr, "perPage": 1},
                headers=self._headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return items[0] if items else None

    async def list_records(self, collection: str, filter_expr: str = "", per_page: int = 500) -> list[dict]:
        import httpx
        async with httpx.AsyncClient() as client:
            params = {"perPage": per_page}
            if filter_expr:
                params["filter"] = filter_expr
            resp = await client.get(
                f"{self.base_url}/api/collections/{collection}/records",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("items", [])

    async def update_record(self, collection: str, record_id: str, data: dict) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.base_url}/api/collections/{collection}/records/{record_id}",
                json=data,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def create_record(self, collection: str, data: dict) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/collections/{collection}/records",
                json=data,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def upsert_record(self, collection: str, filter_expr: str, data: dict) -> dict:
        """Update the existing record matching filter_expr, or create one
        if none exists. Used for agency_service_configs, where each
        (re-)implementation should overwrite the current config rather
        than accumulate duplicate rows."""
        existing = await self.get_record(collection, filter_expr)
        if existing:
            return await self.update_record(collection, existing["id"], data)
        return await self.create_record(collection, data)


pocketbase = PocketBaseClient()
