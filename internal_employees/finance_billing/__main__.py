"""
Entry point: python -m internal_employees.finance_billing
"""

import asyncio

from .worker import run_forever

if __name__ == "__main__":
    asyncio.run(run_forever())
