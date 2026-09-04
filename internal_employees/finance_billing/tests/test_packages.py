from ..packages import build_quote_line_items


VALID_SERVICE = {
    "service_slug": "speed_to_lead",
    "tier": "standard",
    "setup_price": 5000.0,
    "monthly_price": 1500.0,
}


def _assert_raises_value_error(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return
    raise AssertionError("expected ValueError, none was raised")


def test_builds_both_setup_and_monthly_line_items():
    items = build_quote_line_items(VALID_SERVICE)
    assert len(items) == 2
    assert items[0]["rate"] == 5000.0
    assert items[1]["rate"] == 1500.0


def test_uses_actual_record_price_not_a_recomputed_default():
    """The whole point: setup_price/monthly_price on the record is the
    real agreed deal, even if it differs from a generic tier default —
    never override it."""
    negotiated = {**VALID_SERVICE, "setup_price": 3500.0}  # a discounted deal
    items = build_quote_line_items(negotiated)
    assert items[0]["rate"] == 3500.0


def test_omits_setup_line_item_when_zero_or_none():
    no_setup = {**VALID_SERVICE, "setup_price": 0}
    items = build_quote_line_items(no_setup)
    assert len(items) == 1
    assert "Monthly" in items[0]["name"]


def test_omits_monthly_line_item_when_zero_or_none():
    one_time_only = {**VALID_SERVICE, "monthly_price": None}
    items = build_quote_line_items(one_time_only)
    assert len(items) == 1
    assert "Setup" in items[0]["name"]


def test_missing_service_slug_or_tier_raises():
    _assert_raises_value_error(build_quote_line_items, {"setup_price": 100})


def test_no_price_at_all_raises_rather_than_guessing():
    _assert_raises_value_error(build_quote_line_items, {"service_slug": "voice_agent", "tier": "standard"})


def test_both_prices_zero_raises():
    _assert_raises_value_error(
        build_quote_line_items,
        {"service_slug": "voice_agent", "tier": "standard", "setup_price": 0, "monthly_price": 0},
    )


def test_description_includes_package_boundaries_when_provided():
    boundaries = {"included_every_tier": ["lead source connection", "AI qualification calls"]}
    items = build_quote_line_items(VALID_SERVICE, boundaries)
    assert "lead source connection" in items[0]["description"]


def test_description_empty_when_no_boundaries_provided():
    items = build_quote_line_items(VALID_SERVICE, None)
    assert items[0]["description"] == ""


def test_unknown_service_slug_falls_back_to_the_raw_slug_as_display_name():
    unknown = {**VALID_SERVICE, "service_slug": "some_new_service_not_yet_in_the_display_map"}
    items = build_quote_line_items(unknown)
    assert "some_new_service_not_yet_in_the_display_map" in items[0]["name"]
