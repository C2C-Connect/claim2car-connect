"""POSIX original-byte storage component, not an upload or authorization API.

The root and its ancestors must be administrator-controlled persistent storage.
Callers must authorize actor/session access and keep expected digests in a
separate trusted journal. UUID namespacing alone is not tenant authorization.
Requires local filesystem atomic hard links and fsync; no network-FS guarantee.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

class ArtifactConflict(ValueError):
    pass

class ArtifactIntegrityError(ValueError):
    pass

class ArtifactNotFound(LookupError):
    pass

class ArtifactStorageUnavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class ArtifactKey:
    tenant_id: UUID
    session_id: UUID
    artifact_id: UUID

    def __post_init__(self):
        if any(not isinstance(v, UUID) for v in (self.tenant_id, self.session_id, self.artifact_id)):
            raise ValueError('UUID_ARTIFACT_KEY_REQUIRED')

@dataclass(frozen=True)
class ArtifactReceipt:
    key: ArtifactKey
    sha256_hex: str
    byte_length: int
    created: bool

class OriginalByteStore:
    def __init__(self, root, *, max_bytes=25 * 1024 * 1024):
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError('INVALID_ARTIFACT_LIMIT')
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError('ABSOLUTE_STORAGE_ROOT_REQUIRED')
        self.max_bytes = max_bytes

    @staticmethod
    def _validate(key, expected_sha256):
        if not isinstance(key, ArtifactKey):
            raise ValueError('INVALID_ARTIFACT_KEY')
        if not isinstance(expected_sha256, str) or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
            raise ValueError('INVALID_EXPECTED_DIGEST')

    @contextmanager
    def _directory(self, key, *, create):
        fds = []
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            fds.append(os.open(self.root, flags))
            for part in (str(key.tenant_id), str(key.session_id)):
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fds[-1])
                    except FileExistsError:
                        pass
                    os.fsync(fds[-1])
                fds.append(os.open(part, flags, dir_fd=fds[-1]))
            yield fds[-1]
        finally:
            for fd in reversed(fds):
                os.close(fd)

    def _read(self, directory, name, expected):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > self.max_bytes:
                raise ArtifactIntegrityError('INVALID_STORED_ARTIFACT')
            data = source.read(self.max_bytes + 1)
        if not data or len(data) > self.max_bytes or sha256(data).hexdigest() != expected:
            raise ArtifactIntegrityError('ARTIFACT_HASH_MISMATCH')
        return data

    def put(self, key, data, *, expected_sha256):
        self._validate(key, expected_sha256)
        if type(data) is not bytes or not data or len(data) > self.max_bytes:
            raise ValueError('INVALID_ARTIFACT_BYTES')
        if sha256(data).hexdigest() != expected_sha256:
            raise ArtifactIntegrityError('ARTIFACT_HASH_MISMATCH')
        name = str(key.artifact_id) + '.original'
        try:
            with self._directory(key, create=True) as directory:
                pending = '.' + uuid4().hex + '.pending'
                fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
                try:
                    with os.fdopen(fd, 'wb') as target:
                        target.write(data)
                        target.flush()
                        os.fsync(target.fileno())
                    try:
                        os.link(pending, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
                        created = True
                    except FileExistsError:
                        try:
                            existing = self._read(directory, name, expected_sha256)
                        except ArtifactIntegrityError as exc:
                            raise ArtifactConflict('ARTIFACT_ALREADY_EXISTS_WITH_DIFFERENT_BYTES') from exc
                        if existing != data:
                            raise ArtifactConflict('ARTIFACT_ALREADY_EXISTS_WITH_DIFFERENT_BYTES')
                        created = False
                    os.fsync(directory)
                finally:
                    os.unlink(pending, dir_fd=directory)
                    os.fsync(directory)
            return ArtifactReceipt(key, expected_sha256, len(data), created)
        except OSError:
            raise ArtifactStorageUnavailable('ARTIFACT_STORAGE_UNAVAILABLE') from None

    def get(self, key, *, expected_sha256):
        self._validate(key, expected_sha256)
        try:
            with self._directory(key, create=False) as directory:
                return self._read(directory, str(key.artifact_id) + '.original', expected_sha256)
        except FileNotFoundError:
            # A missing administrator-provisioned root is an outage, not a missing artifact.
            if not self.root.is_dir():
                raise ArtifactStorageUnavailable('ARTIFACT_STORAGE_UNAVAILABLE') from None
            raise ArtifactNotFound('ARTIFACT_NOT_FOUND') from None
        except OSError:
            raise ArtifactStorageUnavailable('ARTIFACT_STORAGE_UNAVAILABLE') from None
