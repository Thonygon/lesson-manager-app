import json
import unittest
from io import BytesIO
from urllib.request import Request

import check_synthetic_restore as restore


class FakeResponse(BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class SyntheticRestoreTest(unittest.TestCase):
    def test_capture_and_verify_three_preserved_families(self):
        fixtures = {"payments": "12", "classes": "34", "profiles": "synthetic-user"}
        def source(request: Request, timeout: int):
            self.assertNotIn("synthetic-private-value", request.full_url)
            table = request.full_url.split("/rest/v1/")[1].split("?")[0]
            return FakeResponse(json.dumps([{restore.TABLE_KEYS[table]: fixtures[table], "note": "synthetic-private-value"}]).encode())
        baseline = restore.compare(fixtures, base="https://source.example", key="secret", open_url=source)
        self.assertNotIn("synthetic-private-value", json.dumps(baseline))
        restore.compare(fixtures, base="https://restored.example", key="secret", expected=baseline, open_url=source)
        def altered(request: Request, timeout: int):
            table = request.full_url.split("/rest/v1/")[1].split("?")[0]
            note = "changed" if table == "payments" else "synthetic-private-value"
            return FakeResponse(json.dumps([{restore.TABLE_KEYS[table]: fixtures[table], "note": note}]).encode())
        with self.assertRaisesRegex(RuntimeError, "payments"):
            restore.compare(fixtures, base="https://restored.example", key="secret", expected=baseline, open_url=altered)

    def test_rejects_missing_family_and_mismatched_ids(self):
        with self.assertRaises(ValueError):
            restore.compare({"payments": "1"}, base="https://example.org", key="secret")
        with self.assertRaises(ValueError):
            restore.compare({"payments": "1", "classes": "2", "profiles": "3"}, base="https://example.org", key="secret", expected={"fixtures": {}})


if __name__ == "__main__":
    unittest.main()
