"""
Single async HTTP boundary for the employees.

httpx is imported lazily inside the call, deliberately: it keeps every
module importable (and the logic unit-testable) in environments where
httpx isn't installed.
"""

from typing import Any


async def request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    json: Any | None = None,
    headers: dict | None = None,
) -> Any:
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.request(method, url, params=params, json=json, headers=headers)
        resp.raise_for_status()
        return resp.json()
