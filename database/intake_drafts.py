"""Controlled-test VIN drafts over the existing capture-session event journal.
No HTTP routes, driver login, images, consent or production-intake claim.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from uuid import UUID

class DraftConflict(ValueError):
    pass

class DraftAccessDenied(PermissionError):
    pass

@dataclass(frozen=True)
class IntakeDraft:
    session_id: str
    revision: int
    vin: str | None
    replayed: bool = False
    scope: str = 'controlled-test-vin-draft'

def normalized_vin(value):
    if not isinstance(value,str) or len(value)!=17 or not re.fullmatch('[A-HJ-NPR-Z0-9]{17}',value):
        raise ValueError('NORMALIZED_VIN_REQUIRED')
    values=dict(zip('ABCDEFGHJKLMNPRSTUVWXYZ',[1,2,3,4,5,6,7,8,1,2,3,4,5,7,9,2,3,4,5,6,7,8,9]))
    weights=[8,7,6,5,4,3,2,10,0,9,8,7,6,5,4,3,2]
    remainder=sum((int(c) if c.isdigit() else values[c])*w for c,w in zip(value,weights))%11
    if value[8]!=('X' if remainder==10 else str(remainder)):
        raise ValueError('CHECKSUM_MISMATCH')
    return value

class IntakeDraftStore:
    def __init__(self,sessions):
        self.sessions=sessions

    def _rows(self,conn,actor,session_id):
        rows=conn.execute('SELECT sequence,kind,actor,payload_json,event_id FROM faos.events '
                          'WHERE tenant_id=%s AND session_id=%s ORDER BY sequence LIMIT 1001',
                          (actor.tenant_id,session_id)).fetchall()
        if not rows or len(rows)>1000:
            raise DraftConflict('UNSUPPORTED_INTAKE_HISTORY')
        snapshots=[]
        for index,(sequence,kind,creator,payload,event_id) in enumerate(rows):
            if sequence!=index+1:
                raise DraftConflict('UNSUPPORTED_INTAKE_HISTORY')
            if index==0:
                if kind!='SESSION_CREATED' or event_id!='capture-created':
                    raise DraftConflict('UNSUPPORTED_INTAKE_HISTORY')
                continue
            try:
                data=json.loads(payload)
                valid=(kind=='VEHICLE_RECORDED' and creator==actor.actor_id and type(data) is dict
                       and set(data)=={'contract','request_id','expected_revision','vin'}
                       and data['contract']=='controlled-test-vin-draft-v1'
                       and type(data['expected_revision']) is int and data['expected_revision']==sequence-1
                       and str(UUID(data['request_id']))==data['request_id']
                       and event_id=='intake-draft:'+data['request_id']
                       and normalized_vin(data['vin'])==data['vin'])
                if not valid:raise ValueError()
            except (ValueError,TypeError,KeyError,AttributeError):
                raise DraftConflict('UNSUPPORTED_INTAKE_HISTORY') from None
            snapshots.append((sequence,data))
        return rows,snapshots

    def _open(self,conn,actor,session_id):
        session=self.sessions._read(conn,actor,session_id)
        if session.created_by!=actor.actor_id:
            raise DraftAccessDenied('INTAKE_OWNER_REQUIRED')
        conn.execute('SELECT faos.lock_session_for_completion(%s::uuid,%s::text)',(actor.tenant_id,session_id))
        return self._rows(conn,actor,session_id)

    def get(self,authorization,session_id):
        session_id=self.sessions._identifier(session_id)
        with self.sessions._authorized(authorization) as (conn,actor):
            rows,snapshots=self._open(conn,actor,session_id)
            return IntakeDraft(session_id,rows[-1][0],snapshots[-1][1]['vin'] if snapshots else None)

    def save(self,authorization,session_id,*,request_id,expected_revision,vin):
        session_id=self.sessions._identifier(session_id)
        request_id=str(UUID(str(request_id)))
        if type(expected_revision) is not int or expected_revision<1:
            raise ValueError('INVALID_REVISION')
        vin=normalized_vin(vin)
        payload={'contract':'controlled-test-vin-draft-v1','request_id':request_id,
                 'expected_revision':expected_revision,'vin':vin}
        with self.sessions._authorized(authorization) as (conn,actor):
            rows,snapshots=self._open(conn,actor,session_id)
            for sequence,old in snapshots:
                if old['request_id']==request_id:
                    if old!=payload:raise DraftConflict('IDEMPOTENCY_CONFLICT')
                    return IntakeDraft(session_id,sequence,old['vin'],True)
            if rows[-1][0]!=expected_revision:
                raise DraftConflict('REVISION_CONFLICT')
            if len(rows)>=1000:raise DraftConflict('DRAFT_HISTORY_LIMIT')
            sequence=expected_revision+1
            result=conn.execute('SELECT faos.append_event(%s::uuid,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                                (actor.tenant_id,session_id,'intake-draft:'+request_id,sequence,'VEHICLE_RECORDED',actor.actor_id,
                                 datetime.now(timezone.utc).isoformat(),'controlled test VIN draft save',
                                 json.dumps(payload,sort_keys=True,separators=(',',':')),'0.1')).fetchone()[0]
            if result!='ACCEPTED':raise DraftConflict('DRAFT_SAVE_NOT_ACCEPTED')
            return IntakeDraft(session_id,sequence,vin)
