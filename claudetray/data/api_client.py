"""Optional Anthropic API client for rate limit polling.

When an API key is configured, polls the count_tokens endpoint (free)
to read rate limit headers. Completely optional — the app works fine
without it using only the statusline file.
"""

import threading
from datetime import datetime
from typing import Callable, Optional

import requests

COUNT_TOKENS_URL = "https://api.anthropic.com/v1/messages/count_tokens"
POLL_MODEL = "claude-sonnet-4-6"


class ApiRateLimits:
    __slots__ = (
        "requests_limit", "requests_remaining", "requests_reset",
        "tokens_limit", "tokens_remaining", "tokens_reset",
        "timestamp",
    )

    def __init__(self):
        self.requests_limit: int = 0
        self.requests_remaining: int = 0
        self.requests_reset: Optional[str] = None
        self.tokens_limit: int = 0
        self.tokens_remaining: int = 0
        self.tokens_reset: Optional[str] = None
        self.timestamp: Optional[datetime] = None

    @property
    def requests_used_pct(self) -> float:
        if self.requests_limit <= 0:
            return 0.0
        return (1 - self.requests_remaining / self.requests_limit) * 100

    @property
    def tokens_used_pct(self) -> float:
        if self.tokens_limit <= 0:
            return 0.0
        return (1 - self.tokens_remaining / self.tokens_limit) * 100


def _parse_rate_limits(headers: dict) -> ApiRateLimits:
    rl = ApiRateLimits()
    rl.requests_limit = int(headers.get("anthropic-ratelimit-requests-limit", 0))
    rl.requests_remaining = int(headers.get("anthropic-ratelimit-requests-remaining", 0))
    rl.requests_reset = headers.get("anthropic-ratelimit-requests-reset")
    rl.tokens_limit = int(headers.get("anthropic-ratelimit-tokens-limit", 0))
    rl.tokens_remaining = int(headers.get("anthropic-ratelimit-tokens-remaining", 0))
    rl.tokens_reset = headers.get("anthropic-ratelimit-tokens-reset")
    rl.timestamp = datetime.now()
    return rl


class AnthropicPoller:
    """Periodically polls the Anthropic API for rate limit info."""

    def __init__(self, api_key: str, on_update: Callable[[ApiRateLimits], None],
                 interval: int = 60):
        self._api_key = api_key
        self._on_update = on_update
        self._interval = interval
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self.last_result: Optional[ApiRateLimits] = None
        self.last_error: Optional[str] = None

    def start(self):
        self._running = True
        self._poll()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()

    def _poll(self):
        if not self._running:
            return
        try:
            resp = requests.post(
                COUNT_TOKENS_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": POLL_MODEL,
                    "messages": [{"role": "user", "content": "x"}],
                },
                timeout=10,
            )
            if resp.status_code in (200, 429):
                rl = _parse_rate_limits(resp.headers)
                self.last_result = rl
                self.last_error = None
                self._on_update(rl)
            else:
                self.last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            self.last_error = str(e)

        if self._running:
            self._timer = threading.Timer(self._interval, self._poll)
            self._timer.daemon = True
            self._timer.start()
