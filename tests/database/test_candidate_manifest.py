"""Filesystem-only candidate guard tests; not migration execution evidence."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.candidate_manifest import REQUIRED, snapshot, compare

class CandidateManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in REQUIRED:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        def git(command, **kwargs):
            return (str(self.root) + '\n').encode() if '--show-toplevel' in command else b'fixed-head\n'
        mock = patch('scripts.candidate_manifest.subprocess.check_output', side_effect=git)
        mock.start()
        self.addCleanup(mock.stop)
    def migration(self):
        return self.root / 'migrations/0003_extra.sql'
    def assert_changed(self, before):
        with self.assertRaisesRegex(SystemExit, '^CANDIDATE_CHANGED_DURING_RUN$'):
            compare(before, snapshot())
    def test_unchanged_candidate_compares(self):
        before = snapshot()
        self.assertIsNone(compare(before, snapshot()))
    def test_extra_migration_hashed_exactly(self):
        data = b'SELECT 3;\r\n'
        self.migration().write_bytes(data)
        rows = {row['path']: row for row in snapshot()['files']}
        self.assertEqual(rows['migrations/0003_extra.sql'], {'path':'migrations/0003_extra.sql','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    def test_added_migration_detected(self):
        before = snapshot()
        self.migration().write_text('SELECT 3;')
        self.assert_changed(before)
    def test_modified_migration_detected(self):
        self.migration().write_text('SELECT 3;')
        before = snapshot()
        self.migration().write_text('SELECT 4;')
        self.assert_changed(before)
    def test_removed_extra_migration_detected(self):
        self.migration().write_text('SELECT 3;')
        before = snapshot()
        self.migration().unlink()
        self.assert_changed(before)
    def test_missing_required_file_rejected(self):
        (self.root / 'database/journal.py').unlink()
        with self.assertRaisesRegex(ValueError, '^REQUIRED_FILE_MISSING:database/journal.py$'):
            snapshot()
    def test_symlink_migration_rejected(self):
        self.migration().symlink_to(self.root / 'migrations/0001_tenant_registry.sql')
        with self.assertRaisesRegex(ValueError, '^INVALID_CANDIDATE_PATH:migrations/0003_extra.sql$'):
            snapshot()
    def test_symlink_migration_directory_rejected(self):
        directory = self.root / 'migrations'
        moved = self.root / 'moved-migrations'
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, '^INVALID_CANDIDATE_PATH:migrations$'):
            snapshot()
    def test_rows_sorted_and_unique(self):
        self.migration().write_text('SELECT 3;')
        result = snapshot()
        paths = [row['path'] for row in result['files']]
        self.assertEqual(paths, sorted(set(paths)))
        self.assertEqual(result['head'], 'fixed-head')

if __name__ == '__main__':
    unittest.main()
