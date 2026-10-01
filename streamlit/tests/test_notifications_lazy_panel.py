import unittest
from unittest.mock import patch

from helpers import notifications


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class NotificationLazyPanelTests(unittest.TestCase):
    def test_lazy_panel_skips_loader_when_closed(self):
        loader_called = {"value": False}

        def _loader():
            loader_called["value"] = True
            return [{"signature": "a"}]

        with (
            patch.object(notifications, "_inject_notification_styles"),
            patch.object(notifications.st, "toggle", return_value=False, create=True),
            patch.object(notifications.st, "markdown", create=True),
        ):
            notifications.render_lazy_notification_panel(
                scope="student",
                toggle_key="student_home_notifications_toggle",
                loader=_loader,
                title_text="Notifications",
            )

        self.assertFalse(loader_called["value"])

    def test_lazy_panel_loads_notifications_when_opened(self):
        loader_called = {"value": 0}

        def _loader():
            loader_called["value"] += 1
            return [{"signature": "a", "category": "updates", "message": "Hello"}]

        with (
            patch.object(notifications, "_inject_notification_styles"),
            patch.object(notifications.st, "toggle", return_value=True, create=True),
            patch.object(notifications.st, "markdown", create=True),
            patch.object(notifications, "render_notification_heading"),
            patch.object(notifications, "render_notification_panel"),
        ):
            notifications.render_lazy_notification_panel(
                scope="teacher",
                toggle_key="teacher_dashboard_notifications_toggle",
                loader=_loader,
                title_text="Notifications",
            )

        self.assertEqual(1, loader_called["value"])

    def test_lazy_panel_swallow_loader_errors(self):
        def _loader():
            raise RuntimeError("boom")

        with (
            patch.object(notifications, "_inject_notification_styles"),
            patch.object(notifications.st, "toggle", return_value=True, create=True),
            patch.object(notifications.st, "markdown", create=True),
            patch.object(notifications, "render_notification_heading"),
            patch.object(notifications, "render_notification_panel"),
        ):
            notifications.render_lazy_notification_panel(
                scope="student",
                toggle_key="student_home_notifications_toggle",
                loader=_loader,
                title_text="Notifications",
            )


if __name__ == "__main__":
    unittest.main()
