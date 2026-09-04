from datetime import date

from ..guardrails import default_expiry_date, assert_never_marked_sent, DEFAULT_QUOTE_VALIDITY_DAYS


def test_default_expiry_date_is_30_days_out():
    result = default_expiry_date(date(2026, 1, 1))
    assert result == "2026-01-31"


def test_default_expiry_date_uses_today_when_not_given():
    result = default_expiry_date()
    from datetime import timedelta
    expected = (date.today() + timedelta(days=DEFAULT_QUOTE_VALIDITY_DAYS)).isoformat()
    assert result == expected


def test_assert_never_marked_sent_accepts_drafted_and_blocked():
    assert_never_marked_sent("drafted")
    assert_never_marked_sent("blocked")  # should not raise


def test_assert_never_marked_sent_rejects_sent():
    try:
        assert_never_marked_sent("sent")
    except ValueError:
        return
    raise AssertionError("expected ValueError when status is 'sent'")


def test_assert_never_marked_sent_rejects_paid():
    try:
        assert_never_marked_sent("paid")
    except ValueError:
        return
    raise AssertionError("expected ValueError when status is 'paid'")
