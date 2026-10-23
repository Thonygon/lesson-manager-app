import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE = (Path(__file__).resolve().parents[1] / "services/ai_economic_events.py").read_text(encoding="utf-8")


class FakeTable:
    def __init__(self, name, writes):
        self.name = name
        self.writes = writes
        self.method = ""
        self.payload = None

    def insert(self, payload):
        self.method, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.method, self.payload = "update", payload
        return self

    def eq(self, _column, _value):
        return self

    def execute(self):
        self.writes.append((self.name, self.method, self.payload))
        return types.SimpleNamespace(data=[{"id": 1}])


class FakeDb:
    def __init__(self):
        self.writes = []

    def table(self, name):
        return FakeTable(name, self.writes)


def load_service(db):
    core = types.ModuleType("core")
    core.__path__ = []
    database = types.ModuleType("core.database")
    database.get_sb = lambda: db
    state = types.ModuleType("core.state")
    state.get_current_user_id = lambda: "00000000-0000-4000-8000-000000000001"
    module = types.ModuleType("test_classio_ai_economic_events")
    with patch.dict(sys.modules, {"core": core, "core.database": database, "core.state": state, module.__name__: module}):
        exec(compile(SOURCE, "ai_economic_events.py", "exec"), module.__dict__)
    return module


class AiEconomicEventsTests(unittest.TestCase):
    def test_failed_attempt_then_success_share_one_operation(self):
        db = FakeDb()
        service = load_service(db)
        service.note_functional_event("quick_lesson_ai", "requested")
        first = service.start_provider_attempt("openrouter", "free-model")
        service.finish_provider_attempt(first, "failed", error_kind="timeout")
        second = service.start_provider_attempt("gemini", "gemini-model")
        service.finish_provider_attempt(second, "success", {"usage_metadata": {"prompt_token_count": 12, "candidates_token_count": 6, "prompt": "never-store"}})
        service.note_functional_event("quick_lesson_ai", "success")
        operations = [payload for table, method, payload in db.writes if table == "classio_ai_operations" and method == "insert"]
        attempts = [payload for table, method, payload in db.writes if table == "classio_provider_attempts" and method == "insert"]
        self.assertEqual(len(operations), 1)
        self.assertEqual([row["attempt_no"] for row in attempts], [1, 2])
        self.assertTrue(all(row["operation_id"] == operations[0]["operation_id"] for row in attempts))
        self.assertIsNone(service.provider_usage("openai", {})["input_tokens"])
        self.assertNotIn("never-store", str(db.writes))

    def test_database_failure_prevents_provider_call(self):
        class FailedDb(FakeDb):
            def table(self, _name):
                raise RuntimeError("database unavailable")
        service = load_service(FailedDb())
        called = []
        with self.assertRaisesRegex(RuntimeError, "telemetry could not start"):
            service.run_recorded_provider_attempt("openai", "model", lambda: called.append(True), lambda value: value)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
