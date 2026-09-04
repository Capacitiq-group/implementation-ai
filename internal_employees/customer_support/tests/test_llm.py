import asyncio

from ..integrations.llm import parse_draft_response, draft_and_score


def test_valid_response_parses_correctly():
    reply, confidence = parse_draft_response('{"reply": "Here is your answer.", "confidence": 0.92}')
    assert reply == "Here is your answer."
    assert confidence == 0.92


def test_malformed_json_falls_back_to_zero_confidence():
    reply, confidence = parse_draft_response("this is not json at all")
    assert confidence == 0.0
    assert "could not be parsed" in reply.lower()


def test_missing_reply_field_falls_back_to_zero_confidence():
    reply, confidence = parse_draft_response('{"confidence": 0.9}')
    assert confidence == 0.0


def test_missing_confidence_field_falls_back_to_zero_confidence():
    reply, confidence = parse_draft_response('{"reply": "Here is your answer."}')
    assert confidence == 0.0


def test_non_numeric_confidence_falls_back_to_zero():
    reply, confidence = parse_draft_response('{"reply": "Hi", "confidence": "very sure"}')
    assert confidence == 0.0


def test_empty_reply_falls_back_to_zero_confidence_even_with_high_confidence_claimed():
    """A model claiming high confidence in an empty reply is exactly the
    kind of malformed output that must never slip through as a real
    draft."""
    reply, confidence = parse_draft_response('{"reply": "", "confidence": 0.99}')
    assert confidence == 0.0


def test_out_of_range_confidence_is_rejected_not_clamped():
    reply, confidence = parse_draft_response('{"reply": "Hi", "confidence": 1.5}')
    assert confidence == 0.0
    reply2, confidence2 = parse_draft_response('{"reply": "Hi", "confidence": -0.2}')
    assert confidence2 == 0.0


def test_boundary_confidence_values_are_accepted():
    _, c0 = parse_draft_response('{"reply": "Hi", "confidence": 0.0}')
    _, c1 = parse_draft_response('{"reply": "Hi", "confidence": 1.0}')
    assert c0 == 0.0
    assert c1 == 1.0


def test_draft_and_score_returns_zero_confidence_when_model_not_configured():
    """No mocking needed — OLLAMA_MODEL is unset by default in any
    environment that hasn't explicitly configured it, and this must
    never attempt a network call in that state."""
    reply, confidence = asyncio.run(draft_and_score("system prompt", {"ticket_subject": "test"}))
    assert confidence == 0.0
    assert "not wired" in reply.lower() or "ollama_model" in reply.lower()
