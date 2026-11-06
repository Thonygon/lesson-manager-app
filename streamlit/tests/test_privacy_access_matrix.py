import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from scripts import check_privacy_access_matrix as matrix


class PrivacyAccessMatrixQueryTests(unittest.TestCase):
    def test_selects_the_identifier_present_on_each_private_table(self):
        expected = {
            "worksheets": "id",
            "resource_exposures": "exposure_id",
            "classio_help_tickets": "id",
            "classio_legal_acceptances": "user_id",
        }
        for table, column in expected.items():
            with self.subTest(table=table), patch.object(matrix, "_read", return_value=(200, json.dumps([{column: "fixture"}]).encode())) as read:
                status, count = matrix._rows("https://example.supabase.co", "key", "token", table, {column: "eq.fixture"})
                self.assertEqual((status, count), (200, 1))
                self.assertEqual(parse_qs(urlparse(read.call_args.args[0]).query)["select"], [column])


if __name__ == "__main__":
    unittest.main()
