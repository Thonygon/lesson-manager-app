from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services import operational_diagnostics_service as diagnostics
from app_pages import operational_diagnostics as diagnostics_page


class _RpcCall:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


class _FakeSupabase:
    def __init__(self, *, rpc_data=None, rpc_error: Exception | None = None, table_rows=None):
        self.rpc_data = rpc_data or []
        self.rpc_error = rpc_error
        self.table_rows = table_rows or []
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        if self.rpc_error:
            raise self.rpc_error
        return _RpcCall(self.rpc_data)

    def table(self, name):
        return _TableCall(self.table_rows)


class _TableCall:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.row_limit = None

    def select(self, columns, **kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, value):
        self.row_limit = int(value)
        return self

    def execute(self):
        rows = [
            dict(row)
            for row in self.rows
            if all(row.get(key) == value for key, value in self.filters)
        ]
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        return SimpleNamespace(data=rows)


def _raised_error(message: str = "failure") -> RuntimeError:
    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        return exc


class OperationalDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        diagnostics._RECENT_FINGERPRINTS.clear()

    def tearDown(self):
        diagnostics._RECENT_FINGERPRINTS.clear()

    def test_sanitizer_removes_sensitive_values(self):
        raw = (
            "student@example.com token=secret-value "
            "https://classio.app/path?answer=private "
            "123e4567-e89b-42d3-a456-426614174000"
        )

        safe = diagnostics.sanitize_text(raw)

        self.assertNotIn("student@example.com", safe)
        self.assertNotIn("secret-value", safe)
        self.assertNotIn("answer=private", safe)
        self.assertNotIn("123e4567", safe)
        self.assertIn("[redacted-email]", safe)
        self.assertIn("[redacted]", safe)

    def test_context_uses_an_allowlist_and_sanitizes_values(self):
        safe = diagnostics.sanitize_context(
            {
                "resource_type": "exam",
                "resource_id": "student@example.com",
                "answer_payload": {"answer": "private"},
                "token": "secret",
                "record_count": 4,
            }
        )

        self.assertEqual("exam", safe["resource_type"])
        self.assertEqual("[redacted-email]", safe["resource_id"])
        self.assertEqual(4, safe["record_count"])
        self.assertNotIn("answer_payload", safe)
        self.assertNotIn("token", safe)

    def test_fingerprint_is_stable_and_ignores_dynamic_message_text(self):
        first = _raised_error("student one")
        second = _raised_error("student two")

        first_fingerprint = diagnostics.build_fingerprint(first, component="grading", operation="save")
        second_fingerprint = diagnostics.build_fingerprint(second, component="grading", operation="save")

        self.assertEqual(first_fingerprint, second_fingerprint)
        self.assertNotEqual(
            first_fingerprint,
            diagnostics.build_fingerprint(second, component="grading", operation="regrade"),
        )

    def test_capture_uses_rpc_and_returns_persisted_reference(self):
        persisted_id = "1d170d96-6c61-4498-a81a-b2c8bd2ca560"
        fake_sb = _FakeSupabase(
            rpc_data=[{"captured_event_id": persisted_id, "captured_occurrence_count": 2}]
        )
        exc = _raised_error("student@example.com token=private")

        with (
            patch.object(diagnostics, "get_sb", return_value=fake_sb),
            patch.object(diagnostics, "get_current_user_role", return_value="student"),
            patch.dict(os.environ, {"CLASSIO_DIAGNOSTICS_ENABLED": "true", "CLASSIO_RELEASE": "release-1"}),
        ):
            event_id = diagnostics.capture_exception(
                exc,
                component="grading",
                operation="save_attempt",
                page_key="student_assignments",
                context={"resource_type": "exam", "answer_payload": "private"},
            )

        self.assertEqual(persisted_id, event_id)
        self.assertEqual(diagnostics.DIAGNOSTICS_RPC, fake_sb.calls[0][0])
        params = fake_sb.calls[0][1]
        self.assertEqual("student", params["p_user_face"])
        self.assertEqual("release-1", params["p_release_version"])
        self.assertNotIn("student@example.com", params["p_safe_message"])
        self.assertNotIn("answer_payload", params["p_context_json"])

    def test_capture_failure_never_raises_into_the_user_flow(self):
        fake_sb = _FakeSupabase(rpc_error=RuntimeError("diagnostics table unavailable"))

        with patch.object(diagnostics, "get_sb", return_value=fake_sb):
            event_id = diagnostics.capture_exception(
                _raised_error(),
                component="router",
                operation="render_page",
            )

        self.assertRegex(event_id, r"^[0-9a-f-]{36}$")

    def test_capture_skips_rpc_without_authenticated_user(self):
        fake_sb = _FakeSupabase()

        with (
            patch.object(diagnostics, "get_sb", return_value=fake_sb),
            patch.object(diagnostics, "get_current_user_id", return_value=""),
        ):
            event_id = diagnostics.capture_exception(
                _raised_error(),
                component="router",
                operation="render_page",
            )

        self.assertRegex(event_id, r"^[0-9a-f-]{36}$")
        self.assertEqual([], fake_sb.calls)

    def test_local_suppression_prevents_streamlit_rerun_write_storms(self):
        fake_sb = _FakeSupabase()
        exc = _raised_error()

        with patch.object(diagnostics, "get_sb", return_value=fake_sb):
            first = diagnostics.capture_exception(exc, component="router", operation="render_page")
            second = diagnostics.capture_exception(exc, component="router", operation="render_page")

        self.assertEqual(1, len(fake_sb.calls))
        self.assertEqual(first, second)

    def test_short_reference_does_not_expose_full_identifier(self):
        reference = diagnostics.short_event_reference("1d170d96-6c61-4498-a81a-b2c8bd2ca560")

        self.assertEqual("ERR-1D170D96", reference)
        self.assertNotIn("6c61", reference)

    def test_status_updates_use_the_restricted_rpc_and_are_audited(self):
        event_id = "1d170d96-6c61-4498-a81a-b2c8bd2ca560"
        fake_sb = _FakeSupabase(
            rpc_data=True,
            table_rows=[{"event_id": event_id, "status": "open", "resolution_note": None}],
        )

        with (
            patch.object(diagnostics, "get_sb", return_value=fake_sb),
            patch.object(diagnostics, "require_capability") as require_capability,
            patch.object(diagnostics, "record_privileged_action", return_value=True) as record_action,
        ):
            ok, _message = diagnostics.update_diagnostic_status(
                event_id,
                status="resolved",
                resolution_note="Fixed in release 12",
            )

        self.assertTrue(ok)
        require_capability.assert_called_once_with(diagnostics.CAPABILITY_MANAGE_OPERATIONAL_DIAGNOSTICS)
        self.assertEqual("update_application_diagnostic_status", fake_sb.calls[0][0])
        self.assertEqual("resolved", fake_sb.calls[0][1]["p_status"])
        record_action.assert_called_once()

    def test_diagnostics_page_requires_server_side_workspace_access(self):
        with patch.object(
            diagnostics_page,
            "require_capability",
            side_effect=RuntimeError("streamlit.stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "streamlit.stop"):
                diagnostics_page.render_operational_diagnostics()

    def test_migration_uses_rpc_capture_rls_and_restricted_updates(self):
        migration = Path("migrations/add_operational_diagnostics.sql").read_text(encoding="utf-8")

        self.assertIn("enable row level security", migration)
        self.assertIn("record_application_diagnostic", migration)
        self.assertIn("update_application_diagnostic_status", migration)
        self.assertIn("redact_application_diagnostic_text", migration)
        self.assertIn("revoke insert, delete, update", migration)
        self.assertIn("role_key = 'developer'", migration)
        self.assertIn(">= 30", migration)


if __name__ == "__main__":
    unittest.main()
