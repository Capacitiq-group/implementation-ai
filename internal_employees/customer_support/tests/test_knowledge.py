from ..knowledge import build_kb_filter


def test_filter_always_scopes_to_published_articles():
    filter_expr = build_kb_filter("invoice question")
    assert "is_published = true" in filter_expr


def test_filter_matches_each_significant_word():
    filter_expr = build_kb_filter("billing invoice question")
    for word in ["billing", "invoice", "question"]:
        assert word in filter_expr


def test_filter_drops_short_words():
    filter_expr = build_kb_filter("how do I pay")
    # "how", "do", "i" are <=2 chars and should be dropped; "pay" kept
    assert "pay" in filter_expr
    assert "'do'" not in filter_expr


def test_empty_query_still_scopes_to_published_only():
    filter_expr = build_kb_filter("   ")
    assert filter_expr == "is_published = true"


def test_single_quotes_in_query_are_escaped():
    filter_expr = build_kb_filter("what's my plan")
    # Should not produce a raw, unescaped single quote inside a filter literal
    # that would break PocketBase's filter parser.
    assert "what" in filter_expr  # sanity: word still present in some form
    assert filter_expr.count("'") % 2 == 0  # quotes remain balanced
