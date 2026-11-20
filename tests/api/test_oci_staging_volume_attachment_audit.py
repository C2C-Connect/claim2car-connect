import unittest
from scripts.oci_staging_volume_attachment_audit import AuditError,audit
I="ocid1.instance.x"; P="ocid1.volume.p"; E="ocid1.volume.e"
def r(v,d): return {"volumeId":v,"device":d,"lifecycleState":"ATTACHED","attachmentType":"paravirtualized"}
class TestAudit(unittest.TestCase):
 def test_valid(self):
  out=audit({"data":[r(P,"/dev/oracleoci/a"),r(E,"/dev/oracleoci/b")]},I,P,E); self.assertTrue(out["control_plane_verified"]); self.assertFalse(out["guest_device_probe_performed"])
 def test_same_ids(self):
  with self.assertRaisesRegex(AuditError,"EXPECTED_VOLUME_IDS_INVALID"): audit({"data":[]},I,P,P)
 def test_missing(self):
  with self.assertRaisesRegex(AuditError,"ATTACHMENT_COUNT_INVALID:evidence"): audit({"data":[r(P,"/dev/a")]},I,P,E)
 def test_duplicate(self):
  with self.assertRaisesRegex(AuditError,"ATTACHMENT_COUNT_INVALID:postgres"): audit({"data":[r(P,"/dev/a"),r(P,"/dev/b"),r(E,"/dev/c")]},I,P,E)
 def test_state(self):
  p=r(P,"/dev/a"); p["lifecycleState"]="ATTACHING"
  with self.assertRaisesRegex(AuditError,"VOLUME_NOT_ATTACHED:postgres"): audit({"data":[p,r(E,"/dev/b")]},I,P,E)
 def test_type(self):
  p=r(P,"/dev/a"); p["attachmentType"]="iscsi"
  with self.assertRaisesRegex(AuditError,"ATTACHMENT_TYPE_INVALID:postgres"): audit({"data":[p,r(E,"/dev/b")]},I,P,E)
 def test_collision(self):
  with self.assertRaisesRegex(AuditError,"DEVICE_COLLISION:evidence"): audit({"data":[r(P,"/dev/a"),r(E,"/dev/a")]},I,P,E)
 def test_invalid_path(self):
  with self.assertRaisesRegex(AuditError,"DEVICE_PATH_INVALID:postgres"): audit({"data":[r(P,"/dev/../bad"),r(E,"/dev/b")]},I,P,E)
 def test_payload(self):
  with self.assertRaisesRegex(AuditError,"ATTACHMENT_LIST_INVALID"): audit({"data":{}},I,P,E)
if __name__=="__main__": unittest.main()
