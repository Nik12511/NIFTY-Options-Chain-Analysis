"""Small HTTPS client with per-instance throttling and bounded transient retries."""

import json
import logging
import math
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from nifty_options.config import get_settings

logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class HttpRequestError(RuntimeError):
    """Raised after a non-retryable or exhausted HTTP request."""


class HttpResponseTooLarge(HttpRequestError):
    """Raised when a response exceeds the configured byte limit."""


class HttpClient:
    """Client configured from safe local settings; one instance per provider."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        interval = self.settings.http_min_interval_seconds
        wait = interval - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _retry_after(headers: Any | None, fallback: float) -> float:
        value = headers.get("Retry-After") if headers else None
        if not value:
            return fallback
        try:
            seconds = float(value)
            return max(0.0, min(seconds, 120.0)) if math.isfinite(seconds) else fallback
        except ValueError:
            try:
                when = parsedate_to_datetime(value)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
                return max(0.0, min((when - datetime.now(UTC)).total_seconds(), 120.0))
            except TypeError, ValueError, OverflowError:
                return fallback

    def get_bytes(self, url: str, *, headers: Mapping[str, str] | None = None) -> bytes:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(
                "HTTP data sources must use HTTPS and cannot embed credentials in the URL"
            )
        request = Request(url, headers=dict(headers or {}), method="GET")
        host = parsed.hostname
        for attempt in range(1, self.settings.http_max_attempts + 1):
            self._throttle()
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    payload = cast(bytes, response.read(self.settings.http_max_response_bytes + 1))
                    if len(payload) > self.settings.http_max_response_bytes:
                        raise HttpResponseTooLarge("HTTP response exceeds configured size limit")
                    return payload
            except HTTPError as error:
                if (
                    error.code not in RETRYABLE_STATUS_CODES
                    or attempt >= self.settings.http_max_attempts
                ):
                    logger.error(
                        "HTTP request to %s failed with status %s after attempt %s",
                        host,
                        error.code,
                        attempt,
                    )
                    raise HttpRequestError(
                        f"HTTP request to {host} failed with status {error.code}"
                    ) from error
                delay = self._retry_after(error.headers, min(2 ** (attempt - 1), 30))
                error.close()
                logger.warning(
                    "Transient HTTP status %s from %s; retry %s/%s after %.1f seconds",
                    error.code,
                    host,
                    attempt,
                    self.settings.http_max_attempts,
                    delay,
                )
                time.sleep(delay)
            except (TimeoutError, ConnectionError, URLError) as error:
                if attempt >= self.settings.http_max_attempts:
                    logger.error(
                        "HTTP request to %s failed after %s attempts (%s)",
                        host,
                        attempt,
                        type(error).__name__,
                    )
                    raise HttpRequestError(
                        f"HTTP request to {host} failed after {attempt} attempts"
                    ) from error
                delay = min(2 ** (attempt - 1), 30)
                logger.warning(
                    "Transient network error from %s (%s); retry %s/%s after %s seconds",
                    host,
                    type(error).__name__,
                    attempt,
                    self.settings.http_max_attempts,
                    delay,
                )
                time.sleep(delay)
        raise HttpRequestError(f"HTTP request to {host} failed")

    def get_json(self, url: str, *, headers: Mapping[str, str] | None = None) -> Any:
        try:
            return json.loads(self.get_bytes(url, headers=headers))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            host = urlsplit(url).hostname or "unknown host"
            raise HttpRequestError(f"HTTP response from {host} was not valid UTF-8 JSON") from error
