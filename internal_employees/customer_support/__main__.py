"""
Entry point: python -m ai_worker_customer_support
"""

import asyncio

from .worker import run_forever

if __name__ == "__main__":
    asyncio.run(run_forever())
