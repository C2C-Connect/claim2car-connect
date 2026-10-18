"""Filesystem/mocked-connection preflight tests, not SQL execution tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import database.migrate as migrate


class TestMigrationPreflight(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / 'migrations'
        self.directory.mkdir()
        location = patch.object(migrate, '__file__', str(self.root / 'database' / 'migrate.py'))
        location.start()
        self.addCleanup(location.stop)
        connector = patch.object(migrate.psycopg, 'connect')
        self.connect = connector.start()
        self.addCleanup(connector.stop)
        self.conn = Mock()
        self.connect.return_value.__enter__.return_value = self.conn

    def test_missing_directory_rejected_before_connection(self):
        self.directory.rmdir()
        with self.assertRaisesRegex(ValueError, '^MIGRATIONS_NOT_FOUND$'):
            migrate.run_migrations()
        self.connect.assert_not_called()

    def test_empty_directory_rejected_before_connection(self):
        with self.assertRaisesRegex(ValueError, '^MIGRATIONS_NOT_FOUND$'):
            migrate.run_migrations()
        self.connect.assert_not_called()

    def test_later_blank_file_rejected_before_any_execution(self):
        (self.directory / '0001_valid.sql').write_text('SELECT 1;', encoding='utf-8')
        (self.directory / '0002_blank.sql').write_text(' \n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, r'^EMPTY_MIGRATION:0002_blank\.sql$'):
            migrate.run_migrations()
        self.connect.assert_not_called()
        self.conn.execute.assert_not_called()

    def test_module_relative_files_execute_in_filename_order(self):
        (self.directory / '0002_second.sql').write_text('SELECT 2;', encoding='utf-8')
        (self.directory / '0001_first.sql').write_text('SELECT 1;', encoding='utf-8')
        migrate.run_migrations()
        self.connect.assert_called_once()
        self.assertEqual(self.connect.call_args.kwargs, {'autocommit': True})
        self.assertEqual(self.conn.execute.call_args_list, [call('SELECT 1;'), call('SELECT 2;')])


if __name__ == '__main__':
    unittest.main()
