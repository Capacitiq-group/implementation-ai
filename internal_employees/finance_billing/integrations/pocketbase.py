"""
PocketBase client for the Agency instance. Record CRUD comes from
_framework/pocketbase.py; the only employee-specific part is the auth
mode — a scoped, non-superuser service token (see README for the exact,
deliberately narrow collection access this employee needs).
"""

from ..._framework.pocketbase import BasePocketBaseClient
from ..config import settings


class AgencyPocketBaseClient(BasePocketBaseClient):
    def __init__(self) -> None:
        super().__init__(settings.pocketbase_url)
        self.token = settings.pocketbase_service_token

    async def headers(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    def _headers(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    async def get_record(self, collection: str, filter_expr: str) -> dict | None:
        """This employee looks records up by filter, not by id."""
        return await self.find_first(collection, filter_expr)


pocketbase = AgencyPocketBaseClient()
