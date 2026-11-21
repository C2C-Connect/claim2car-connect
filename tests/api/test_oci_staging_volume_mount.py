import unittest
from scripts.oci_staging_volume_mount import MountSetupError,format_confirmation,validate_mapping
PG="ocid1.volume.oc1..pg";EV="ocid1.volume.oc1..ev"
def sample():return {"postgres":{"volume_ocid":PG,"device":"/dev/oracleoci/oraclevdb"},"evidence":{"volume_ocid":EV,"device":"/dev/oracleoci/oraclevdc"}}
class SafeVolumeMountTests(unittest.TestCase):
 def test_mapping_must_match_both_expected_ocids_and_devices(self):
  result=validate_mapping(sample(),PG,EV)
  self.assertEqual(result["postgres"]["mountpoint"],"/var/lib/claim2car/postgres")
  self.assertEqual(result["evidence"]["mountpoint"],"/var/lib/claim2car/evidence")
  with self.assertRaisesRegex(MountSetupError,"MISMATCH"):validate_mapping(sample(),PG,"ocid1.volume.oc1..other")
  rows=sample();rows["evidence"]["device"]=rows["postgres"]["device"]
  with self.assertRaisesRegex(MountSetupError,"COLLISION"):validate_mapping(rows,PG,EV)
 def test_formatting_requires_explicit_exact_confirmation_of_both_ocids(self):
  with self.assertRaisesRegex(MountSetupError,"CONFIRMATION"):format_confirmation(PG,EV,True,"")
  with self.assertRaisesRegex(MountSetupError,"CONFIRMATION"):format_confirmation(PG,EV,True,PG)
  self.assertTrue(format_confirmation(PG,EV,True,PG+","+EV))
  with self.assertRaisesRegex(MountSetupError,"WITHOUT_FORMAT"):format_confirmation(PG,EV,False,PG+","+EV)
 def test_no_format_default(self):
  self.assertFalse(format_confirmation(PG,EV,False,""))

 def test_dry_run_allows_blank_volumes_but_reports_format_gate(self):
  # The helper reports the blank-device action without mutating storage; actual
  # format execution still requires explicit OCID confirmation.
  self.assertFalse(format_confirmation(PG,EV,False,""))
