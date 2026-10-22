"""Exact-byte migration planning for reviewed UTF-8, transaction-compatible SQL."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

@dataclass(frozen=True)
class Migration:
    name: str
    sha256: str
    sql: str

def discover(directory):
    paths = sorted(Path(directory).glob('*.sql'))
    if not paths:
        raise ValueError('MIGRATIONS_NOT_FOUND')
    result = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError('INVALID_MIGRATION_FILE:' + path.name)
        if not re.fullmatch(r'[0-9]{4}_[a-z0-9_]+\.sql', path.name):
            raise ValueError('INVALID_MIGRATION_NAME:' + path.name)
        data = path.read_bytes()
        sql = data.decode('utf-8')
        if not sql.strip():
            raise ValueError('EMPTY_MIGRATION:' + path.name)
        result.append(Migration(path.name, hashlib.sha256(data).hexdigest(), sql))
    versions = [item.name.split('_', 1)[0] for item in result]
    if len(set(versions)) != len(versions):
        raise ValueError('DUPLICATE_MIGRATION_VERSION')
    return tuple(result)

def discover_authority(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    plan = tuple(sorted(discover(root/'migrations') + discover(root/'authority_migrations'),key=lambda item:item.name))
    versions = [item.name.split('_',1)[0] for item in plan]
    if len(versions) != len(set(versions)):
        raise ValueError('DUPLICATE_MIGRATION_VERSION')
    return plan

def pending(candidate, history):
    history = tuple(history)
    if len(history) > len(candidate):
        raise ValueError('MIGRATION_HISTORY_NOT_PREFIX')
    for migration, applied in zip(candidate, history):
        if migration.name != applied[0]:
            raise ValueError('MIGRATION_HISTORY_NOT_PREFIX')
        if migration.sha256 != applied[1]:
            raise ValueError('APPLIED_MIGRATION_CHANGED:' + migration.name)
    return candidate[len(history):]
