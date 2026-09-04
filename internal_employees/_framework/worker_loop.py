"""The poll loop every employee runs: do one cycle, sleep, repeat."""

import asyncio
from typing import Awaitable, Callable


async def run_forever(run_once: Callable[[], Awaitable[None]], poll_interval_seconds: int) -> None:
    while True:
        await run_once()
        await asyncio.sleep(poll_interval_seconds)
