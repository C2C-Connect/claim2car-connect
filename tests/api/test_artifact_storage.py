"""Actual local-filesystem tests; no API, PostgreSQL, device or hosting claims."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID
from app.artifact_storage import (ArtifactKey, OriginalByteStore, ArtifactConflict,
    ArtifactIntegrityError, ArtifactNotFound, ArtifactStorageUnavailable)

class OriginalByteStoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = OriginalByteStore(self.root, max_bytes=1024)
        self.key = ArtifactKey(UUID(int=1), UUID(int=2), UUID(int=3))
        self.data = b'original synthetic bytes\x00\xff'
        self.digest = sha256(self.data).hexdigest()

    def put(self, data=None):
        data = self.data if data is None else data
        return self.store.put(self.key, data, expected_sha256=sha256(data).hexdigest())

    def path(self):
        return self.root / str(self.key.tenant_id) / str(self.key.session_id) / (str(self.key.artifact_id) + '.original')

    def test_preserves_original_bytes_and_receipt(self):
        receipt = self.put()
        self.assertTrue(receipt.created)
        self.assertEqual(receipt.byte_length, len(self.data))
        self.assertEqual(self.store.get(self.key, expected_sha256=self.digest), self.data)

    def test_same_retry_is_stable(self):
        self.put()
        self.assertFalse(self.put().created)

    def test_conflicting_retry_does_not_overwrite(self):
        self.put()
        with self.assertRaises(ArtifactConflict):
            self.put(b'other bytes')
        self.assertEqual(self.path().read_bytes(), self.data)

    def test_retrieval_rejects_tampering(self):
        self.put()
        self.path().write_bytes(b'tampered')
        with self.assertRaises(ArtifactIntegrityError):
            self.store.get(self.key, expected_sha256=self.digest)

    def test_rejects_invalid_keys_and_limits(self):
        with self.assertRaises(ValueError):
            ArtifactKey('../escape', UUID(int=2), UUID(int=3))
        for value in (b'', b'x' * 1025, 'not bytes'):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                self.store.put(self.key, value, expected_sha256=self.digest)
        with self.assertRaises(ValueError):
            self.store.get(self.key, expected_sha256='bad')

    def test_wrong_incoming_digest_writes_nothing(self):
        with self.assertRaises(ArtifactIntegrityError):
            self.store.put(self.key, self.data, expected_sha256='0' * 64)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_namespace_separation(self):
        self.put()
        for key in (ArtifactKey(UUID(int=4), self.key.session_id, self.key.artifact_id),
                    ArtifactKey(self.key.tenant_id, UUID(int=4), self.key.artifact_id)):
            with self.assertRaises(ArtifactNotFound):
                self.store.get(key, expected_sha256=self.digest)

    def test_concurrent_identical_writers_create_once(self):
        with ThreadPoolExecutor(max_workers=8) as workers:
            receipts = list(workers.map(lambda _: self.put(), range(16)))
        self.assertEqual(sum(r.created for r in receipts), 1)
        self.assertEqual(list(self.path().parent.glob('*.pending')), [])

    def test_new_process_recovers_original(self):
        self.put()
        code = ('from app.artifact_storage import *; from uuid import UUID; '
                'import sys; key=ArtifactKey(UUID(int=1),UUID(int=2),UUID(int=3)); '
                'sys.stdout.buffer.write(OriginalByteStore(sys.argv[1]).get(key,expected_sha256=sys.argv[2]))')
        result = subprocess.run([sys.executable, '-c', code, str(self.root), self.digest], check=True, capture_output=True)
        self.assertEqual(result.stdout, self.data)

    def test_failed_publication_does_not_commit_partial_artifact(self):
        with patch('app.artifact_storage.os.link', side_effect=OSError('synthetic failure')):
            with self.assertRaises(ArtifactStorageUnavailable):
                self.put()
        self.assertFalse(self.path().exists())
        self.assertEqual(list(self.path().parent.glob('*.pending')), [])
        self.assertTrue(self.put().created)

    def test_symlink_directory_is_rejected(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (self.root / str(self.key.tenant_id)).symlink_to(outside.name, target_is_directory=True)
        with self.assertRaises(ArtifactStorageUnavailable):
            self.put()
        self.assertEqual(list(Path(outside.name).iterdir()), [])

    def test_symlink_artifact_is_not_followed(self):
        self.put()
        self.path().unlink()
        other = self.root / 'outside'
        other.write_bytes(self.data)
        self.path().symlink_to(other)
        with self.assertRaises(ArtifactStorageUnavailable):
            self.store.get(self.key, expected_sha256=self.digest)

if __name__ == '__main__':
    unittest.main()
