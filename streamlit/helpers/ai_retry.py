import time
from typing import Callable, TypeVar


T = TypeVar("T")


_NON_RETRYABLE_ERROR_MARKERS = (
    "401",
    "403",
    "invalid api key",
    "invalid_api_key",
    "incorrect api key",
    "user not found",
    "permission denied",
    "unauthorized",
    "forbidden",
    "missing_openrouter_api_key",
    "missing_gemini_api_key",
    "missing_openai_api_key",
)

_RETRYABLE_ERROR_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "deadline exceeded",
    "high demand",
    "internal server error",
    "overloaded",
    "rate limit",
    "service unavailable",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "unavailable",
)


def is_retryable_ai_error(exc: Exception) -> bool:
    message = str(exc or "").strip().lower()
    if not message:
        return False

    if any(marker in message for marker in _NON_RETRYABLE_ERROR_MARKERS):
        return False

    return any(marker in message for marker in _RETRYABLE_ERROR_MARKERS)


def run_with_ai_retries(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    initial_delay_seconds: float = 1.0,
) -> T:
    last_error = None

    for attempt in range(max_attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts - 1 or not is_retryable_ai_error(exc):
                raise
            time.sleep(initial_delay_seconds * (attempt + 1))

    raise RuntimeError(str(last_error or "AI request failed"))
