"""Unit tests for OCI persistent-volume identity and format safety."""
import unittest
from scripts.oci_staging_volume_mount import MountSetupError,validate_format_confirmation,validate_mapping
PG="ocid1.volume.oc1..postgres";EV="ocid1.volume.oc1..evidence"
def sample():
    return {"postgres":{"volume_ocid":PG,"device":"/dev/oracleoci/oraclevdb"},"evidence":{"volume_ocid":EV,"device":"/dev/oracleoci/oraclevdc"}}
class SafeVolumeMountTests(unittest.TestCase):
    def test_exact_mapping_and_targets(self):
        m=validate_mapping(sample(),PG,EV)
        self.assertEqual(m["postgres"]["mountpoint"],"/var/lib/claim2car/postgres")
        self.assertEqual(m["evidence"]["mountpoint"],"/var/lib/claim2car/evidence")
        with self.assertRaisesRegex(MountSetupError,"MISMATCH"):validate_mapping(sample(),PG,"ocid1.volume.oc1..other")
        m=sample();m["evidence"]["device"]=m["postgres"]["device"]
        with self.assertRaisesRegex(MountSetupError,"COLLISION"):validate_mapping(m,PG,EV)
    def test_format_confirmation_requires_exact_both_ids(self):
        with self.assertRaisesRegex(MountSetupError,"CONFIRMATION"):validate_format_confirmation(PG,EV,True,"")
        with self.assertRaisesRegex(MountSetupError,"CONFIRMATION"):validate_format_confirmation(PG,EV,True,PG)
        validate_format_confirmation(PG,EV,True,PG+","+EV)
        with self.assertRaisesRegex(MountSetupError,"WITHOUT_FORMAT"):validate_format_confirmation(PG,EV,False,PG+","+EV)
    def test_format_is_disabled_by_default(self):
        validate_format_confirmation(PG,EV,False,"")
