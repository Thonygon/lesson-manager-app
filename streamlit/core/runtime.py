from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
import os
from typing import Any


UtcClock = Callable[[], datetime]
MonotonicTimer = Callable[[], float]


def configure_joblib_cpu_count() -> None:
    """Give loky a safe fallback when physical CPU discovery is unavailable."""
    if not str(os.environ.get("LOKY_MAX_CPU_COUNT") or "").strip():
        os.environ["LOKY_MAX_CPU_COUNT"] = "1"


def utc_now(clock: UtcClock | None = None) -> datetime:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resolve_utc_datetime(value: Any = None, *, clock: UtcClock | None = None) -> datetime:
    if isinstance(value, datetime):
        resolved = value
    else:
        text = str(value or "").strip()
        if not text:
            return utc_now(clock)
        resolved = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if resolved.tzinfo is None:
        resolved = resolved.replace(tzinfo=timezone.utc)
    return resolved.astimezone(timezone.utc)


def elapsed_seconds(started_at: float, timer: MonotonicTimer, *, digits: int = 6) -> float:
    return round(max(0.0, float(timer()) - float(started_at)), max(0, int(digits)))


def without_nondeterministic_fields(value: Any, field_names: Iterable[str]) -> Any:
    excluded = {str(name) for name in field_names}
    if isinstance(value, dict):
        return {
            key: without_nondeterministic_fields(item, excluded)
            for key, item in value.items()
            if str(key) not in excluded
        }
    if isinstance(value, list):
        return [without_nondeterministic_fields(item, excluded) for item in value]
    if isinstance(value, tuple):
        return tuple(without_nondeterministic_fields(item, excluded) for item in value)
    return value
