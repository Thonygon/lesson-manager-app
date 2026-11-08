"""Guard the prototype against bypassing reviewed account erasure."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AccountDeletionBoundaryTests(unittest.TestCase):
    def test_prototype_uses_private_request_instead_of_service_role_deletion(self):
        profile = (ROOT / "auth/auth.py").read_text(encoding="utf-8")
        database = (ROOT / "core/database.py").read_text(encoding="utf-8")
        self.assertIn("app.masterclassio.com/help?from=%2Fprofile&kind=privacy_rights&scope=erasure", profile)
        self.assertNotIn("delete_user_data(", profile + database)
        self.assertNotIn('rpc("classio_delete_account_data"', database)


if __name__ == "__main__":
    unittest.main()
