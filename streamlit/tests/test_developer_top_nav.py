import unittest

from app_pages.router import _developer_workspace_nav_items


class DeveloperTopNavTests(unittest.TestCase):
    def test_developer_pages_remain_adjacent_with_all_face_switches(self):
        items = _developer_workspace_nav_items(
            "Operational Diagnostics (2)",
            can_teach=True,
            can_study=True,
            is_admin=True,
        )

        keys = [key for key, _label, _icon in items]
        self.assertEqual(
            ["developer_workspace", "operational_diagnostics"],
            keys[:2],
        )
        self.assertEqual(
            ["switch_teacher", "switch_student", "switch_admin", "profile", "sign_out"],
            keys[2:],
        )

    def test_developer_pages_remain_adjacent_without_face_switches(self):
        items = _developer_workspace_nav_items(
            "Operational Diagnostics",
            can_teach=False,
            can_study=False,
            is_admin=False,
        )

        self.assertEqual(
            ["developer_workspace", "operational_diagnostics", "profile", "sign_out"],
            [key for key, _label, _icon in items],
        )


if __name__ == "__main__":
    unittest.main()
