import types
import unittest
from unittest.mock import patch

from core import database


class LedgerClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return self

    def execute(self):
        if len(self.calls) == 1:
            raise TimeoutError("response lost after commit")
        return types.SimpleNamespace(data={"id": 12, "replayed": True})


class TeacherLedgerRetryTests(unittest.TestCase):
    def test_uncertain_response_reuses_request_id(self):
        client = LedgerClient()
        state = {}
        with patch.object(database, "get_current_user_id", return_value="00000000-0000-0000-0000-000000000001"), \
             patch.object(database, "get_sb", return_value=client), \
             patch.object(database, "clear_app_caches"), \
             patch.object(database, "st", types.SimpleNamespace(session_state=state)):
            with self.assertRaises(TimeoutError):
                database._mutate_teacher_ledger("payment", "delete", 12)
            result = database._mutate_teacher_ledger("payment", "delete", 12)
        self.assertTrue(result["replayed"])
        self.assertEqual(client.calls[0][1]["p_request_id"], client.calls[1][1]["p_request_id"])
        self.assertEqual(client.calls[0][1]["p_user_id"], "00000000-0000-0000-0000-000000000001")
        self.assertFalse(state)

    def test_signed_out_teacher_cannot_mutate(self):
        with patch.object(database, "get_current_user_id", return_value=None):
            with self.assertRaises(ValueError):
                database._mutate_teacher_ledger("class", "add", None, {"student": "Synthetic"})

    def test_payment_add_retries_with_same_key_and_preserves_bookkeeping_fields(self):
        client = LedgerClient()
        state = {}
        params = dict(student="Synthetic", number_of_lesson=8, payment_date="2026-10-22",
                      paid_amount=160, modality="Online", subject="English",
                      package_start_date="2026-10-23", lesson_adjustment_units=2,
                      package_normalized=True, normalized_note="Synthetic adjustment")
        with patch.object(database, "get_current_user_id", return_value="00000000-0000-0000-0000-000000000001"), \
             patch.object(database, "get_sb", return_value=client), \
             patch.object(database, "clear_app_caches"), \
             patch.object(database, "st", types.SimpleNamespace(session_state=state)):
            with self.assertRaises(TimeoutError):
                database.add_payment(**params)
            database.add_payment(**params)
        first = client.calls[0][1]
        self.assertEqual(first["p_request_id"], client.calls[1][1]["p_request_id"])
        self.assertEqual(first["p_entity"], "payment")
        self.assertEqual(first["p_action"], "add")
        self.assertEqual(first["p_payload"]["lesson_adjustment_units"], 2)
        self.assertTrue(first["p_payload"]["package_normalized"])
        self.assertEqual(first["p_payload"]["normalized_note"], "Synthetic adjustment")
        self.assertFalse(state)


if __name__ == "__main__":
    unittest.main()
