"""Filesystem/planner tests; no database execution."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from database.migration_plan import discover, pending

class MigrationPlanTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
    def put(self, name='0001_first.sql', content=b'SELECT 1;'):
        (self.root/name).write_bytes(content)
    def test_missing(self):
        with self.assertRaisesRegex(ValueError, 'MIGRATIONS_NOT_FOUND'):
            discover(self.root/'missing')
    def test_empty(self):
        with self.assertRaisesRegex(ValueError, 'MIGRATIONS_NOT_FOUND'):
            discover(self.root)
    def test_blank(self):
        self.put(content=b' \n')
        with self.assertRaisesRegex(ValueError, 'EMPTY_MIGRATION'):
            discover(self.root)
    def test_name(self):
        self.put('bad.sql')
        with self.assertRaisesRegex(ValueError, 'INVALID_MIGRATION_NAME'):
            discover(self.root)
    def test_duplicate_version(self):
        self.put(); self.put('0001_other.sql')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_MIGRATION_VERSION'):
            discover(self.root)
    def test_symlink(self):
        self.put(); (self.root/'0002_link.sql').symlink_to(self.root/'0001_first.sql')
        with self.assertRaisesRegex(ValueError, 'INVALID_MIGRATION_FILE'):
            discover(self.root)
    def test_exact_bytes(self):
        raw = b'SELECT 1;\r\n'; self.put(content=raw)
        self.assertEqual(discover(self.root)[0].sha256, hashlib.sha256(raw).hexdigest())
    def test_order(self):
        self.put('0002_second.sql'); self.put()
        self.assertEqual([m.name for m in discover(self.root)], ['0001_first.sql','0002_second.sql'])
    def test_initial(self):
        self.put(); candidate=discover(self.root)
        self.assertEqual(pending(candidate, []), candidate)
    def test_noop(self):
        self.put(); candidate=discover(self.root)
        self.assertEqual(pending(candidate, [(m.name,m.sha256) for m in candidate]), ())
    def test_suffix(self):
        self.put(); self.put('0002_second.sql'); candidate=discover(self.root)
        self.assertEqual(pending(candidate, [(candidate[0].name,candidate[0].sha256)]), candidate[1:])
    def test_changed(self):
        self.put(); candidate=discover(self.root)
        with self.assertRaisesRegex(ValueError, 'APPLIED_MIGRATION_CHANGED'):
            pending(candidate, [(candidate[0].name,'0'*64)])
    def test_unknown_history(self):
        self.put()
        with self.assertRaisesRegex(ValueError, 'MIGRATION_HISTORY_NOT_PREFIX'):
            pending(discover(self.root), [('0000_unknown.sql','0'*64)])
    def test_long_history(self):
        self.put(); candidate=discover(self.root)
        with self.assertRaisesRegex(ValueError, 'MIGRATION_HISTORY_NOT_PREFIX'):
            pending(candidate, [('x','x'),('y','y')])
