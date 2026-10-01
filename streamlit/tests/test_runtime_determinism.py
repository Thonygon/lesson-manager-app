from __future__ import annotations

from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from core.runtime import configure_joblib_cpu_count, elapsed_seconds, resolve_utc_datetime, without_nondeterministic_fields


class RuntimeDeterminismTests(unittest.TestCase):
    def test_joblib_cpu_fallback_replaces_empty_environment_value(self):
        with patch.dict(os.environ, {"LOKY_MAX_CPU_COUNT": ""}):
            configure_joblib_cpu_count()

            self.assertEqual("1", os.environ["LOKY_MAX_CPU_COUNT"])

    def test_resolve_utc_datetime_accepts_fixed_iso_value(self):
        resolved = resolve_utc_datetime("2026-07-15T12:30:00Z")

        self.assertEqual(datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc), resolved)

    def test_elapsed_seconds_uses_injected_monotonic_timer(self):
        self.assertEqual(0.375, elapsed_seconds(10.0, lambda: 10.375))

    def test_nondeterministic_fields_are_removed_recursively(self):
        payload = {
            "duration_ms": 10,
            "rows": [{"score": 1, "duration_ms": 20}],
            "stable": {"value": "kept"},
        }

        self.assertEqual(
            {"rows": [{"score": 1}], "stable": {"value": "kept"}},
            without_nondeterministic_fields(payload, {"duration_ms"}),
        )


if __name__ == "__main__":
    unittest.main()
