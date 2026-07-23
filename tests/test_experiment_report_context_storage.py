import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import experiment_report_context_service as context_service


class ExperimentReportContextStorageTests(unittest.TestCase):
    def test_default_local_storage_does_not_probe_missing_supabase_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(context_service, "REPORT_CONTEXT_ROOT", Path(tmpdir)),
                patch.object(context_service, "get_sb") as get_sb,
                patch.dict(
                    "os.environ",
                    {"EXPERIMENT_REPORT_CONTEXT_STORAGE": "local"},
                    clear=False,
                ),
            ):
                context = context_service.get_report_context("run-1", "experiment-1", "es")

        get_sb.assert_not_called()
        self.assertEqual("run-1", context["run_id"])
        self.assertEqual("es", context["language"])

    def test_default_save_uses_local_cache_without_missing_table_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(context_service, "REPORT_CONTEXT_ROOT", Path(tmpdir)),
                patch.object(context_service, "get_sb") as get_sb,
                patch.object(context_service, "get_current_user_id", return_value="developer-1"),
                patch.dict(
                    "os.environ",
                    {"EXPERIMENT_REPORT_CONTEXT_STORAGE": "local"},
                    clear=False,
                ),
            ):
                saved = context_service.save_report_context(
                    {
                        "run_id": "run-1",
                        "experiment_id": "experiment-1",
                        "language": "es",
                        "business_problem": "Test",
                    }
                )

        get_sb.assert_not_called()
        self.assertEqual("local_cache", saved["_storage_status"])


if __name__ == "__main__":
    unittest.main()
