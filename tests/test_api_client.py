from claudetray.data.api_client import ApiRateLimits, _parse_rate_limits


def test_parse_rate_limits_from_headers():
    headers = {
        "anthropic-ratelimit-requests-limit": "60",
        "anthropic-ratelimit-requests-remaining": "45",
        "anthropic-ratelimit-requests-reset": "2026-06-25T12:00:00Z",
        "anthropic-ratelimit-tokens-limit": "100000",
        "anthropic-ratelimit-tokens-remaining": "80000",
        "anthropic-ratelimit-tokens-reset": "2026-06-25T12:00:00Z",
    }
    rl = _parse_rate_limits(headers)
    assert rl.requests_limit == 60
    assert rl.requests_remaining == 45
    assert rl.tokens_limit == 100000
    assert rl.tokens_remaining == 80000
    assert rl.timestamp is not None


def test_requests_used_pct():
    rl = ApiRateLimits()
    rl.requests_limit = 100
    rl.requests_remaining = 75
    assert rl.requests_used_pct == 25.0


def test_tokens_used_pct():
    rl = ApiRateLimits()
    rl.tokens_limit = 100000
    rl.tokens_remaining = 60000
    assert rl.tokens_used_pct == 40.0


def test_zero_limit_returns_zero_pct():
    rl = ApiRateLimits()
    assert rl.requests_used_pct == 0.0
    assert rl.tokens_used_pct == 0.0


def test_parse_missing_headers():
    rl = _parse_rate_limits({})
    assert rl.requests_limit == 0
    assert rl.tokens_limit == 0
    assert rl.requests_used_pct == 0.0
