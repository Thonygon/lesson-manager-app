from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_migrations import compare_applied_migrations, validate_local_migrations


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class MigrationCheckTests(unittest.TestCase):
    def _workspace(self, migrations: dict[str, str], ledger_entries: list[dict[str, str]]):
        tempdir = tempfile.TemporaryDirectory()
        root = Path(tempdir.name)
        migration_dir = root / "migrations"
        migration_dir.mkdir()
        for name, content in migrations.items():
            (migration_dir / name).write_text(content, encoding="utf-8")
        ledger_path = migration_dir / "ledger.json"
        ledger_path.write_text(json.dumps({"version": 1, "migrations": ledger_entries}), encoding="utf-8")
        return tempdir, migration_dir, ledger_path

    def test_valid_local_ledger_passes(self):
        content = "create table example (id bigint);\n"
        tempdir, migration_dir, ledger_path = self._workspace(
            {"add_example.sql": content},
            [{"name": "add_example.sql", "sha256": _checksum(content)}],
        )
        self.addCleanup(tempdir.cleanup)

        entries, issues = validate_local_migrations(migration_dir, ledger_path)

        self.assertEqual(1, len(entries))
        self.assertEqual([], issues)

    def test_empty_untracked_and_changed_migrations_fail(self):
        original = "create table example (id bigint);\n"
        changed = "create table example (id text);\n"
        tempdir, migration_dir, ledger_path = self._workspace(
            {"add_example.sql": changed, "empty.sql": "-- placeholder\n", "untracked.sql": "select 1;\n"},
            [{"name": "add_example.sql", "sha256": _checksum(original)}],
        )
        self.addCleanup(tempdir.cleanup)

        _entries, issues = validate_local_migrations(migration_dir, ledger_path)
        codes = {issue.code for issue in issues}

        self.assertIn("checksum_mismatch", codes)
        self.assertIn("migration_empty", codes)
        self.assertIn("migration_untracked", codes)

    def test_applied_comparison_detects_missing_changed_and_unknown_rows(self):
        expected = [
            {"name": "one.sql", "sha256": "a" * 64},
            {"name": "two.sql", "sha256": "b" * 64},
        ]
        applied = [
            {"name": "one.sql", "checksum": "c" * 64},
            {"name": "legacy.sql", "checksum": "d" * 64},
        ]

        codes = {issue.code for issue in compare_applied_migrations(expected, applied)}

        self.assertEqual(
            {"applied_checksum_mismatch", "migration_unapplied", "applied_migration_unknown"},
            codes,
        )


if __name__ == "__main__":
    unittest.main()
