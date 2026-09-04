"""Environment reading helpers, so every employee's config.py parses the
same way (and mis-set numeric vars fail loudly at import, not mid-run)."""

import os


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
