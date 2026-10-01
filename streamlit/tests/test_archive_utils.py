import unittest

import pandas as pd

from helpers.archive_utils import (
    ARCHIVED_STATUS,
    filter_archived_rows,
    is_archived_status,
    normalize_status,
    truthy_flag,
)


class ArchiveUtilsTests(unittest.TestCase):
    def test_normalize_status_defaults_to_active(self):
        self.assertEqual(normalize_status(""), "active")
        self.assertEqual(normalize_status(None), "active")

    def test_is_archived_status_detects_archived(self):
        self.assertTrue(is_archived_status("archived"))
        self.assertTrue(is_archived_status(" ARCHIVED "))
        self.assertFalse(is_archived_status("active"))

    def test_filter_archived_rows_excludes_archived_by_default(self):
        df = pd.DataFrame(
            [
                {"id": 1, "status": "active"},
                {"id": 2, "status": ARCHIVED_STATUS},
                {"id": 3, "status": "draft"},
            ]
        )
        filtered = filter_archived_rows(df)
        self.assertEqual(filtered["id"].tolist(), [1, 3])

    def test_filter_archived_rows_can_return_only_archived(self):
        df = pd.DataFrame(
            [
                {"id": 1, "status": "active"},
                {"id": 2, "status": ARCHIVED_STATUS},
            ]
        )
        filtered = filter_archived_rows(df, archived_only=True)
        self.assertEqual(filtered["id"].tolist(), [2])

    def test_truthy_flag_understands_common_string_values(self):
        self.assertTrue(truthy_flag(True))
        self.assertTrue(truthy_flag("true"))
        self.assertTrue(truthy_flag("1"))
        self.assertFalse(truthy_flag(False))
        self.assertFalse(truthy_flag("no"))


if __name__ == "__main__":
    unittest.main()
