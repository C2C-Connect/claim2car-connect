"""Synthetic in-memory completion coverage; not database persistence tests."""
import json
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch
from app.domain_events import DomainEvent
from app.evidence_manifest import ManifestEntry, build_manifest, verify_manifest, load_shot_contract, CANONICAL_SLOTS
from app.synthetic_evidence import reconstruct, manifest_for, evaluate, check_completion

class CompletionCoverage(unittest.TestCase):
    def event(self,n,kind,payload):
        return DomainEvent('synthetic-s',str(n),n,kind,'synthetic-actor','2026-10-18T00:00:00Z',
                           'synthetic fixture',json.dumps(payload,sort_keys=True,separators=(',',':')))
    def append(self,events,kind,payload):
        return events+(self.event(len(events)+1,kind,payload),)
    def fixture(self,omit=None,seal=True):
        events=()
        events=self.append(events,'SESSION_CREATED',{'synthetic':True})
        events=self.append(events,'CONSENT_RECORDED',{'disclosure_version':'synthetic-v1','evidence_scope':True})
        events=self.append(events,'VEHICLE_RECORDED',{'status':'AVAILABLE','reference':'synthetic-vehicle','unavailable_reason':None})
        data={}
        for slot in load_shot_contract()[1]:
            if slot==omit:
                continue
            data[slot]=('SYNTHETIC-NOT-A-PHOTO-'+slot).encode()
            events=self.append(events,'ARTIFACT_REGISTERED',{'artifact_id':slot,'slot':slot,'bytes_hex':data[slot].hex(),'sha256_hex':sha256(data[slot]).hexdigest()})
            events=self.append(events,'QUALITY_RECORDED',{'artifact_id':slot,'passed':True,'method':'synthetic-fixture'})
        digest=manifest_for(reconstruct('synthetic-s',events)).digest() if omit is None else 'missing-root'
        if seal and omit is None:
            events=self.append(events,'MANIFEST_SEALED',{'schema_version':'0.1','shot_list_version':load_shot_contract()[0],'manifest_digest':digest})
        return events,data,digest
    def test_canonical_contract(self):
        version,slots=load_shot_contract()
        self.assertEqual(version,'claims2car-12-v1')
        self.assertEqual(slots,('vin_ocr','doc_ocr','front','front_left','driver_side','rear_left','rear','rear_right','passenger_side','front_right','interior_front','undercarriage_engine'))
    def test_changed_contract_rejected(self):
        value={'schema_version':'0.1','shot_list_version':'claims2car-12-v1','required_angles':list(reversed(CANONICAL_SLOTS))}
        with patch('app.evidence_manifest.Path.read_text',return_value=json.dumps(value)):
            with self.assertRaisesRegex(ValueError,'INVALID_SHOT_CONTRACT'):
                load_shot_contract()
    def test_valid_completion(self):
        e,b,d=self.fixture()
        decision=check_completion('synthetic-s',e,b,d)
        self.assertEqual((decision.status,decision.reasons,decision.event_count),('ELIGIBLE',(),len(e)))
    def test_deterministic_immutable_replay(self):
        e,b,d=self.fixture()
        self.assertEqual(reconstruct('synthetic-s',e),reconstruct('synthetic-s',iter(e)))
        before=tuple(e)
        check_completion('synthetic-s',e,b,d)
        self.assertEqual(e,before)
    def test_every_missing_slot_blocks(self):
        for slot in CANONICAL_SLOTS:
            with self.subTest(slot=slot):
                e,b,d=self.fixture(omit=slot)
                self.assertIn('CAPTURE_SET_INCOMPLETE',evaluate('synthetic-s',e,b,d).reasons)
                with self.assertRaises(ValueError):
                    check_completion('synthetic-s',e,b,d)
    def test_no_seal_blocks(self):
        e,b,d=self.fixture(seal=False)
        self.assertIn('MANIFEST_SEAL_REQUIRED',evaluate('synthetic-s',e,b,d).reasons)
    def test_wrong_seal_snapshot_rejected(self):
        e,b,d=self.fixture(seal=False)
        e=self.append(e,'MANIFEST_SEALED',{'schema_version':'0.1','shot_list_version':'claims2car-12-v1','manifest_digest':'0'*64})
        with self.assertRaisesRegex(ValueError,'SEAL_SNAPSHOT_MISMATCH'):
            reconstruct('synthetic-s',e)
    def test_invalid_seal_fields(self):
        e,b,d=self.fixture()
        with self.assertRaisesRegex(ValueError,'INVALID_SEAL_PAYLOAD'):
            reconstruct('synthetic-s',self.append(e,'MANIFEST_SEALED',{}))
    def test_consent_revocation(self):
        e,b,d=self.fixture()
        e=self.append(e,'CONSENT_RECORDED',{'disclosure_version':'v1','evidence_scope':False})
        self.assertIn('REQUIRED_CONSENT_MISSING',evaluate('synthetic-s',e,b,d).reasons)
    def test_vehicle_unavailable_requires_review(self):
        e,b,d=self.fixture()
        e=self.append(e,'VEHICLE_RECORDED',{'status':'DATA_UNAVAILABLE','reference':None,'unavailable_reason':'lookup failed'})
        self.assertEqual(evaluate('synthetic-s',e,b,d).status,'REVIEW_REQUIRED')
        with self.assertRaises(ValueError):
            check_completion('synthetic-s',e,b,d)
    def test_failed_quality_blocks(self):
        e,b,d=self.fixture()
        e=self.append(e,'QUALITY_RECORDED',{'artifact_id':'front','passed':False,'method':'synthetic-fixture'})
        self.assertIn('QUALITY_NOT_PASSED',evaluate('synthetic-s',e,b,d).reasons)
    def test_missing_quality_blocks(self):
        e,b,d=self.fixture(seal=False)
        filtered=[event for event in e if not (event.kind=='QUALITY_RECORDED' and event.payload['artifact_id']=='front')]
        e=tuple(replace(event,event_id=str(n),sequence=n) for n,event in enumerate(filtered,1))
        e=self.append(e,'MANIFEST_SEALED',{'schema_version':'0.1','shot_list_version':'claims2car-12-v1','manifest_digest':d})
        self.assertIn('QUALITY_NOT_PASSED',evaluate('synthetic-s',e,b,d).reasons)
    def test_tampered_missing_extra_bytes(self):
        e,b,d=self.fixture()
        for data in (dict(b,front=b'changed'),dict(b,extra=b'extra'),{k:v for k,v in b.items() if k!='front'}):
            with self.subTest(keys=tuple(data)):
                with self.assertRaises(ValueError):
                    check_completion('synthetic-s',e,data,d)
    def test_wrong_external_root(self):
        e,b,d=self.fixture()
        self.assertIn('INTEGRITY_NOT_VERIFIED',evaluate('synthetic-s',e,b,'0'*64).reasons)
    def test_cross_session_rejected(self):
        e,b,d=self.fixture()
        with self.assertRaisesRegex(ValueError,'CROSS_SESSION_REFERENCE'):
            check_completion('other',e,b,d)
    def test_note_preserves_eligibility_and_attribution(self):
        e,b,d=self.fixture()
        e=self.append(e,'REVIEW_RECORDED',{'disposition':'NOTE_ONLY','artifact_ids':['front'],'schema_version':'0.1'})
        state=reconstruct('synthetic-s',e)
        self.assertEqual(state.reviews[0].actor,'synthetic-actor')
        self.assertEqual(check_completion('synthetic-s',e,b,d).status,'ELIGIBLE')
    def test_required_review_blocks_completion(self):
        e,b,d=self.fixture()
        e=self.append(e,'REVIEW_RECORDED',{'disposition':'HUMAN_QC_REQUIRED','artifact_ids':['front'],'schema_version':'0.1'})
        self.assertEqual(evaluate('synthetic-s',e,b,d).status,'REVIEW_REQUIRED')
        with self.assertRaises(ValueError):
            check_completion('synthetic-s',e,b,d)
    def test_review_cannot_override(self):
        e,b,d=self.fixture()
        e=self.append(e,'REVIEW_RECORDED',{'disposition':'APPROVE_ANYWAY','artifact_ids':['front'],'schema_version':'0.1'})
        with self.assertRaisesRegex(ValueError,'INVALID_REVIEW'):
            reconstruct('synthetic-s',e)
    def test_bad_record_types_and_schema(self):
        e,b,d=self.fixture()
        for payload in ({'disclosure_version':'v1','evidence_scope':1},{'disclosure_version':'v1','evidence_scope':True,'extra':1},{'disclosure_version':'v1','evidence_scope':True,'schema_version':'unknown'}):
            with self.assertRaises(ValueError):
                reconstruct('synthetic-s',self.append(e,'CONSENT_RECORDED',payload))
    def test_conflicting_artifact(self):
        e,b,d=self.fixture()
        payload=e[3].payload; payload['slot']='rear'
        with self.assertRaisesRegex(ValueError,'CONFLICTING_ARTIFACT'):
            reconstruct('synthetic-s',self.append(e,'ARTIFACT_REGISTERED',payload))
    def test_duplicate_slot(self):
        e,b,d=self.fixture()
        payload=e[3].payload; payload['artifact_id']='another-id'
        with self.assertRaisesRegex(ValueError,'DUPLICATE_CAPTURE_SLOT'):
            reconstruct('synthetic-s',self.append(e,'ARTIFACT_REGISTERED',payload))
    def test_artifact_hash_mismatch(self):
        e,b,d=self.fixture()
        payload=e[3].payload; payload['sha256_hex']='0'*64
        with self.assertRaisesRegex(ValueError,'ARTIFACT_HASH_MISMATCH'):
            reconstruct('synthetic-s',self.append(e,'ARTIFACT_REGISTERED',payload))
    def test_history_order_rejected(self):
        e,b,d=self.fixture()
        with self.assertRaisesRegex(ValueError,'SEQUENCE_CONFLICT'):
            reconstruct('synthetic-s',(e[1],e[0])+e[2:])
    def test_empty_history_blocked(self):
        self.assertEqual(evaluate('synthetic-s',(),{},'').status,'BLOCKED')
    def test_manifest_canonical_order(self):
        e,b,d=self.fixture()
        m=manifest_for(reconstruct('synthetic-s',e))
        self.assertEqual(build_manifest(m.session_id,reversed(m.entries)),m)
        reversed_manifest=replace(m,entries=tuple(reversed(m.entries)))
        self.assertFalse(verify_manifest(m.session_id,reversed_manifest,reversed_manifest.digest(),b))
    def test_manifest_incomplete_and_duplicates(self):
        e,b,d=self.fixture()
        m=manifest_for(reconstruct('synthetic-s',e))
        for entries in (m.entries[:-1],m.entries[:-1]+(m.entries[0],)):
            with self.assertRaisesRegex(ValueError,'CAPTURE_SET_INCOMPLETE_OR_DUPLICATE'):
                build_manifest(m.session_id,entries)
    def test_manifest_bad_entries(self):
        e,b,d=self.fixture()
        m=manifest_for(reconstruct('synthetic-s',e))
        for changes in ({'sha256_hex':'bad'},{'slot':'unknown'},{'artifact_id':''}):
            with self.assertRaisesRegex(ValueError,'INVALID_MANIFEST_ENTRY'):
                build_manifest(m.session_id,(replace(m.entries[0],**changes),)+m.entries[1:])
    def test_manifest_empty_or_nonbytes(self):
        e,b,d=self.fixture()
        m=manifest_for(reconstruct('synthetic-s',e))
        for content in (b'','not bytes',bytearray(b'x')):
            self.assertFalse(verify_manifest('synthetic-s',m,d,dict(b,front=content)))
    def test_manifest_wrong_version(self):
        e,b,d=self.fixture()
        m=manifest_for(reconstruct('synthetic-s',e))
        self.assertFalse(verify_manifest('synthetic-s',replace(m,schema_version='unknown'),d,b))
    def test_unknown_review_reference(self):
        e,b,d=self.fixture()
        e=self.append(e,'REVIEW_RECORDED',{'disposition':'NOTE_ONLY','artifact_ids':['missing'],'schema_version':'0.1'})
        with self.assertRaisesRegex(ValueError,'INVALID_REVIEW_REFERENCES'):
            reconstruct('synthetic-s',e)

if __name__=='__main__':
    unittest.main()
