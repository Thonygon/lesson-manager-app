import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE = (Path(__file__).resolve().parents[1] / "services/document_export_events.py").read_text(encoding="utf-8")


class FakeTable:
    def __init__(self, writes):
        self.writes = writes

    def insert(self, payload):
        self.writes.append(payload)
        return self

    def execute(self):
        return types.SimpleNamespace(data=[{"event_id": self.writes[-1]["event_id"]}])


def load_service(clicked=True, actor_id="00000000-0000-4000-8000-000000000001"):
    writes = []
    st = types.ModuleType("streamlit")
    st.download_button = lambda *args, **kwargs: clicked
    core = types.ModuleType("core")
    core.__path__ = []
    database = types.ModuleType("core.database")
    database.get_sb = lambda: types.SimpleNamespace(table=lambda name: FakeTable(writes) if name == "classio_document_export_events" else None)
    state = types.ModuleType("core.state")
    state.get_current_user_id = lambda: actor_id
    module = types.ModuleType("test_classio_document_export_events")
    with patch.dict(sys.modules, {"streamlit": st, "core": core, "core.database": database, "core.state": state, module.__name__: module}):
        exec(compile(SOURCE, "document_export_events.py", "exec"), module.__dict__)
    return module, writes


class ExportEventsTests(unittest.TestCase):
    def test_clicked_word_button_records_handoff_without_filename_or_content(self):
        service, writes = load_service()
        self.assertTrue(service.recorded_download_button("Word", data=b"private-content", file_name="Ana_student.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", document_kind="worksheet"))
        self.assertEqual(len(writes), 1)
        self.assertEqual((writes[0]["format"], writes[0]["document_kind"], writes[0]["variant"], writes[0]["status"]), ("docx", "worksheet", "student", "handoff_requested"))
        self.assertNotIn("Ana", str(writes))
        self.assertNotIn("private-content", str(writes))

    def test_render_without_click_writes_nothing(self):
        service, writes = load_service(clicked=False)
        self.assertFalse(service.recorded_download_button("PDF", data=b"document", file_name="exam.pdf", mime="application/pdf", document_kind="exam"))
        self.assertEqual(writes, [])

    def test_public_download_has_no_billable_event(self):
        service, writes = load_service(actor_id="")
        self.assertTrue(service.recorded_download_button("PDF", data=b"document", file_name="plan.pdf", mime="application/pdf", document_kind="lesson_plan"))
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
