"""
The actual LLM call for drafting a support reply — against Ollama
(self-hosted), NOT Kimi, which this stack reserves for OCR elsewhere.
Kept separate from drafting.py's SYSTEM_PROMPT (content/guardrail
concerns) — this module is pure transport: send the messages, parse the
response, and hold one critical safety property regardless of what goes
wrong:

**Any failure here — a network error, a bad status code, malformed JSON
in the response, a missing field — must return confidence 0.0, never
raise past this module in a way that could accidentally read as
"succeeded."** worker.py's should_auto_send(0.0) is always False, so a
failure here always self-escalates rather than either crashing the job
ungracefully or, far worse, silently treating a parse failure as a
confident draft. This is the same principle as the rest of this
codebase's guardrails: fail toward review, never toward autonomy.

Lazy httpx import, same reasoning as every other integration in this
codebase — keeps this module importable/testable without httpx
installed.
"""

import json

from ..config import settings

RESPONSE_FORMAT_INSTRUCTION = """

## Required output format

Respond with ONLY a JSON object, no other text, in exactly this shape:
{"reply": "<the reply body text>", "confidence": <a number from 0.0 to 1.0>}

"confidence" must reflect your own honest assessment of how certain you \
are that this reply is fully grounded in the context you were given, \
with nothing invented. A reply that had to say "I'll check and follow \
up" because information was missing is not a low-confidence failure —
score it on whether what you DID say is accurate, not on completeness.
"""


async def draft_and_score(system_prompt: str, context: dict) -> tuple[str, float]:
    """
    Returns (draft_body, confidence). Never raises — any failure mode
    returns a placeholder body and confidence 0.0, per this module's
    docstring above.
    """
    if not settings.ollama_model:
        return "[NOT WIRED — OLLAMA_MODEL is not set to a pulled model.]", 0.0

    full_system_prompt = system_prompt + RESPONSE_FORMAT_INSTRUCTION
    user_message = json.dumps(context, indent=2)

    headers = {"Content-Type": "application/json"}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:  # local inference can be slower than a hosted API
            resp = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": full_system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            raw_content = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"[LLM call failed: {exc!r}]", 0.0

    return parse_draft_response(raw_content)


def parse_draft_response(raw_content: str) -> tuple[str, float]:
    """
    Pure function — no I/O — split out from draft_and_score() specifically
    so parsing correctness (including every malformed-input case) can be
    tested directly, without mocking an HTTP call for each one.
    """
    try:
        parsed = json.loads(raw_content)
        reply = parsed["reply"]
        confidence = float(parsed["confidence"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return f"[LLM response could not be parsed: {raw_content[:200]!r}]", 0.0

    if not isinstance(reply, str) or not reply.strip():
        return "[LLM returned an empty reply.]", 0.0
    if not (0.0 <= confidence <= 1.0):
        # A model returning an out-of-range confidence is itself a signal
        # something's off — don't clamp it and pretend it's fine, treat
        # the whole response as untrustworthy.
        return f"[LLM returned an out-of-range confidence value: {confidence}]", 0.0

    return reply, confidence
