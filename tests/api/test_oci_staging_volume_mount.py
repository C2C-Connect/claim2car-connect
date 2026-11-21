"""Unit tests for OCI persistent-volume identity and format safety."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.oci_staging_volume_mount import MountSetupError,validate_format_confirmation,validate_mapping
from scripts.oci_volume_device_map import write_json_secure
PG="ocid1.volume.oc1..postgres";EV="ocid1.volume.oc1..evidence"
def sample():
    return {"postgres":{"volume_ocid":PG,"device":"/dev/oracleoci/oraclevdb"},"evidence":{"volume_ocid":EV,"device":"/dev/oracleoci/oraclevdc"}}
class SafeVolumeMountTests(unittest.TestCase):
    def test_exact_mapping_and_targets(self):
        m=validate_mapping(sample(),PG,EV)
        self.assertEqual(m["postgres"]["mountpoint"],"/var/lib/claim2car/postgres")
        self.assertEqual(m["evidence"]["mountpoint"],"/var/lib/claim2car/evidence")
        with self.assertRaisesRegex(MountSetupError,"MISMATCH"):validate_mapping(sample(),PG,"ocid1.volume.oc1..other")
        rows=sample();rows["evidence"]["device"]=rows["postgres"]["device"]
        with self.assertRaisesRegex(MountSetupError,"COLLISION"):validate_mapping(rows,PG,EV)
    def test_format_confirmation(self):
        with self.assertRaisesRegex(MountSetupError,"CONFIRMATION"):validate_format_confirmation(PG,EV,True,"")
        with self.assertRaisesRegex(MountSetupError,"CONFIRMATION"):validate_format_confirmation(PG,EV,True,PG)
        validate_format_confirmation(PG,EV,True,PG+","+EV)
        with self.assertRaisesRegex(MountSetupError,"WITHOUT_FORMAT"):validate_format_confirmation(PG,EV,False,PG+","+EV)
    def test_format_disabled_by_default(self):
        validate_format_confirmation(PG,EV,False,"")
    def test_machine_mapping_file_is_private_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"mapping.json";write_json_secure(str(p),sample())
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(p.read_text()),sample())
            link=Path(d)/"link.json";link.symlink_to(p)
            with self.assertRaisesRegex(Exception,"SYMLINK"):write_json_secure(str(link),sample())
