"""Shared provider validation and error-handling utilities."""

from urllib.parse import urlparse

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

PROVIDER_EXCEPTIONS = (
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    APIError,
    APIStatusError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


def validate_http_base_url(value: str, setting_name: str, app_env: str) -> str:
    """Validate OpenAI-compatible HTTP base URL."""

    base_url = value.strip()
    parsed = urlparse(base_url)
    if not base_url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            f"Invalid {setting_name} value. Expected absolute http(s) URL, got: {value!r}."
        )
    if parsed.scheme == "http" and app_env.lower().strip() not in {
        "development",
        "dev",
        "local",
        "test",
    }:
        raise ValueError(
            f"Unsafe {setting_name} value for APP_ENV={app_env!r}. "
            "Use https URL outside local/development environments."
        )
    return base_url
