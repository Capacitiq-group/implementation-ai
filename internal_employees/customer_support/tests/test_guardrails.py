from .. import guardrails


def test_billing_category_always_escalates_regardless_of_wording():
    action = guardrails.choose_submit_action("billing", "Question about my invoice")
    assert action == "support.manage"


def test_account_category_always_escalates():
    action = guardrails.choose_submit_action("account", "How do I update my email address")
    assert action == "support.manage"


def test_sensitive_keyword_escalates_even_in_technical_category():
    action = guardrails.choose_submit_action("technical", "I want to cancel my subscription immediately")
    assert action == "support.manage"


def test_plain_technical_question_is_a_candidate_for_auto_send():
    action = guardrails.choose_submit_action("technical", "How do I reset my password")
    assert action == "email.manage"


def test_should_auto_send_respects_confidence_threshold():
    assert guardrails.should_auto_send(0.95) is True
    assert guardrails.should_auto_send(0.84) is False
    assert guardrails.should_auto_send(0.0) is False


def test_choose_submit_action_never_returns_a_denylisted_or_unpermitted_action():
    """Exhaustive check: every combination of category/subject this
    function could plausibly be fed must only ever produce a member of
    PERMITTED_ACTIONS, never anything in AI_GLOBAL_DENYLIST or outside
    what this employee is actually configured with."""
    categories = ["billing", "technical", "account", "feature_request", "other", "unexpected_new_category"]
    subjects = [
        "normal question", "please cancel my account", "refund now",
        "this is fraud", "", "URGENT LEGAL ACTION",
    ]
    for category in categories:
        for subject in subjects:
            action = guardrails.choose_submit_action(category, subject)
            assert action in guardrails.PERMITTED_ACTIONS
            assert action not in guardrails.AI_GLOBAL_DENYLIST


def test_assert_action_is_safe_accepts_permitted_actions():
    guardrails.assert_action_is_safe("email.manage")
    guardrails.assert_action_is_safe("support.manage")  # should not raise


def test_assert_action_is_safe_rejects_denylisted_action():
    try:
        guardrails.assert_action_is_safe("billing.refund")
        assert False, "should have raised"
    except ValueError as e:
        assert "denylist" in str(e).lower()


def test_assert_action_is_safe_rejects_unpermitted_but_not_denylisted_action():
    try:
        guardrails.assert_action_is_safe("customers.impersonate")
        assert False, "should have raised"
    except ValueError:
        pass  # this one is actually denylisted too, but the point is it raises

    try:
        guardrails.assert_action_is_safe("leads.manage")  # a real permission, not this employee's
        assert False, "should have raised"
    except ValueError as e:
        assert "permitted_actions" in str(e).lower()
