"""
The shared half of the gate protocol.

These two sets mirror synkra-os's ai_jobs.pb.js exactly. The server
enforces them regardless of what this file says; the mirror exists so a
worker can refuse a bad action before submitting it. If the server's
lists change, change these to match — they are not a second source of
truth.
"""

# Mirrors ai_jobs.pb.js AI_GLOBAL_DENYLIST exactly.
AI_GLOBAL_DENYLIST = {
    "billing.refund",
    "billing.modify",
    "customers.impersonate",
    "employees.manage",
    "permissions.manage",
    "infrastructure.restart",
    "deployments.execute",
    "ai.configure",
}

# Mirrors ai_jobs.pb.js ALWAYS_REQUIRES_REVIEW exactly.
ALWAYS_REQUIRES_REVIEW = {
    "customers.edit",
    "support.manage",
}


def assert_action_is_safe(action: str, permitted_actions: set[str]) -> None:
    """Defense in depth: raises if an action is denylisted globally or
    outside the calling employee's own permitted_actions."""
    if action in AI_GLOBAL_DENYLIST:
        raise ValueError(f"Action {action!r} is on the global AI denylist — refusing to submit.")
    if action not in permitted_actions:
        raise ValueError(f"Action {action!r} is not in this employee's permitted_actions — refusing to submit.")
