"""
Thin ElevenLabs wrapper for this repo, independent of synkra-core.
Not wired to a real HTTP call yet — needs your sandbox ElevenLabs API
key and confirmation of the exact Conversational AI agent-creation
endpoint/payload shape before this can be finished (their API has
changed shape before; check current docs when you wire this).
"""

from ..config import settings


async def create_or_update_agent(client_id: str, system_prompt: str) -> dict:
    if settings.environment == "sandbox":
        # TODO: call ElevenLabs sandbox API once credentials exist.
        return {"id": f"el_sandbox_{client_id}", "system_prompt": system_prompt}

    raise NotImplementedError(
        "Production ElevenLabs agent creation not wired yet — confirm the "
        "current Conversational AI API shape before implementing this."
    )
