"""Static opaque service-credential boundary; no HTTP routes or end-user login.

Provision high-entropy tokens out of band; store only SHA-256 digests here.
A resolved login name is not database authorization: the connection layer must
verify its role privileges and the database's live tenant binding separately.
Reload configuration to revoke a credential; expiry is checked on every resolve.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import re
import time
from uuid import UUID

@dataclass(frozen=True)
class ActorBinding:
    actor_id: str
    tenant_id: UUID
    database_role: str

@dataclass(frozen=True)
class Credential:
    token_sha256: str = field(repr=False)
    binding: ActorBinding
    expires_at: int
    enabled: bool = True

class AuthenticationError(ValueError):
    pass

class CredentialResolver:
    def __init__(self,credentials=()):
        records=tuple(credentials)
        digests,actors,roles=set(),{},{}
        for record in records:
            if not isinstance(record,Credential) or not isinstance(record.binding,ActorBinding):
                raise ValueError('INVALID_IDENTITY_CONFIGURATION')
            binding=record.binding
            if (not isinstance(record.token_sha256,str) or re.fullmatch('[0-9a-f]{64}',record.token_sha256) is None
                or type(record.expires_at) is not int or record.expires_at<=0 or type(record.enabled) is not bool
                or not isinstance(binding.tenant_id,UUID) or not isinstance(binding.actor_id,str)
                or not 1<=len(binding.actor_id)<=128 or binding.actor_id.strip()!=binding.actor_id or not binding.actor_id.isprintable()
                or not isinstance(binding.database_role,str) or re.fullmatch('[a-z][a-z0-9_]{0,62}',binding.database_role) is None
                or binding.database_role in ('postgres','faos_app','faos_writer','faos_migrator','faos_fixture')
                or binding.database_role.startswith(('pg_','rds_'))):
                raise ValueError('INVALID_IDENTITY_CONFIGURATION')
            if (record.token_sha256 in digests or (binding.actor_id in actors and actors[binding.actor_id]!=binding)
                or (binding.database_role in roles and roles[binding.database_role]!=binding.tenant_id)):
                raise ValueError('AMBIGUOUS_IDENTITY_CONFIGURATION')
            digests.add(record.token_sha256)
            actors[binding.actor_id]=binding
            roles[binding.database_role]=binding.tenant_id
        self._credentials=records

    def resolve(self,authorization):
        match=re.fullmatch(r'Bearer ([A-Za-z0-9_-]{43,128})',authorization,re.IGNORECASE|re.ASCII) if isinstance(authorization,str) else None
        if match is None:
            raise AuthenticationError('UNAUTHORIZED')
        digest=hashlib.sha256(match.group(1).encode('ascii')).hexdigest()
        now=time.time()
        result=None
        for record in self._credentials:
            matched=hmac.compare_digest(digest,record.token_sha256)
            if matched and record.enabled and now<record.expires_at:
                result=record.binding
        if result is None:
            raise AuthenticationError('UNAUTHORIZED')
        return result
