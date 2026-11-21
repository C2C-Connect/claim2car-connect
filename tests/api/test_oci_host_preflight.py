import importlib.util
from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "oci_staging_network_audit.py"
SPEC = importlib.util.spec_from_file_location("oci_staging_network_audit", MODULE_PATH)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class OciStagingNetworkAuditTests(unittest.TestCase):
    def setUp(self):
        self.subnet = {"data": {
            "vcnId": "vcn-good",
            "prohibitPublicIpOnVnic": True,
            "securityListIds": ["sl-1"],
        }}

    def test_private_subnet_and_allowlisted_ingress_pass(self):
        security_lists = [{"data": {
            "id": "sl-1", "displayName": "private",
            "ingressSecurityRules": [
                {"protocol": "6", "source": "10.0.0.0/16",
                 "tcpOptions": {"destinationPortRange": {"min": 22, "max": 22}}}
            ],
        }}]
        self.assertEqual(AUDIT.audit_network(self.subnet, security_lists, "vcn-good"), [])

    def test_public_ipv4_ingress_is_rejected(self):
        security_lists = [{"data": {
            "id": "sl-1", "displayName": "default",
            "ingressSecurityRules": [{"protocol": "6", "source": "0.0.0.0/0"}],
        }}]
        findings = AUDIT.audit_network(self.subnet, security_lists, "vcn-good")
        self.assertTrue(any(item.startswith("PUBLIC_INGRESS:default:0") for item in findings))

    def test_public_ipv6_ingress_is_rejected(self):
        security_lists = [{"data": {
            "id": "sl-1", "displayName": "default-v6",
            "ingressSecurityRules": [{"protocol": "all", "source": "::/0"}],
        }}]
        findings = AUDIT.audit_network(self.subnet, security_lists, "vcn-good")
        self.assertTrue(any(item.startswith("PUBLIC_INGRESS:default-v6:0") for item in findings))

    def test_subnet_must_be_private_and_belong_to_expected_vcn(self):
        subnet = {"data": {
            "vcnId": "wrong-vcn",
            "prohibitPublicIpOnVnic": False,
            "securityListIds": ["sl-1"],
        }}
        security_lists = [{"data": {"id": "sl-1", "ingressSecurityRules": []}}]
        findings = AUDIT.audit_network(subnet, security_lists, "vcn-good")
        self.assertIn("SUBNET_VCN_MISMATCH", findings)
        self.assertIn("SUBNET_DOES_NOT_PROHIBIT_PUBLIC_IP", findings)

    def test_missing_security_list_response_fails_closed(self):
        findings = AUDIT.audit_network(self.subnet, [], "vcn-good")
        self.assertIn("SECURITY_LIST_RESPONSE_COUNT_MISMATCH", findings)

    def test_malformed_ingress_source_fails_closed(self):
        security_lists = [{"data": {
            "id": "sl-1", "displayName": "broken",
            "ingressSecurityRules": [{"protocol": "6", "source": "not-a-cidr"}],
        }}]
        findings = AUDIT.audit_network(self.subnet, security_lists, "vcn-good")
        self.assertIn("INGRESS_SOURCE_INVALID:broken:0", findings)

    def test_cloud_init_installs_restricted_private_runcommand_deploy_support(self):
        cloud_init = (ROOT / "infra" / "oci" / "staging" / "cloud-init.yaml").read_text()
        terraform = (ROOT / "infra" / "oci" / "staging" / "main.tf").read_text()
        self.assertIn("oci-cli==3.96.3", cloud_init)
        self.assertIn("claim2car-staging-deploy", cloud_init)
        self.assertIn("ocarun ALL=(root) NOPASSWD: /usr/local/sbin/claim2car-staging-deploy", cloud_init)
        self.assertNotIn("NOPASSWD:ALL", cloud_init)
        self.assertIn('"Compute Instance Run Command"', terraform)
        self.assertIn('desired_state = "ENABLED"', terraform)
        self.assertIn("secret-bundle get", cloud_init)
        self.assertIn("compare/${commit}...main", cloud_init)


    def test_cloud_init_preflight_checks_distinct_writable_durable_volumes(self):
        cloud_init = (ROOT / "infra" / "oci" / "staging" / "cloud-init.yaml").read_text()
        marker = "    content: |\n"
        self.assertIn(marker, cloud_init)
        preflight_path = "path: /usr/local/sbin/claim2car-host-preflight\n"
        self.assertIn(preflight_path, cloud_init)
        script_start = cloud_init.index(marker, cloud_init.index(preflight_path)) + len(marker)
        script_end = cloud_init.index("\nruncmd:", script_start)
        script = textwrap.dedent(cloud_init[script_start:script_end])

        self.assertIn('findmnt -rn -o SOURCE --mountpoint "$path"', script)
        self.assertIn('[[ "$postgres_source" != "$evidence_source" ]]', script)
        self.assertIn("runuser -u 10001 -- python3", script)
        self.assertIn('stat -c %u:%g "$path"', script)
        self.assertIn('expected_mode="750"', script)
        self.assertIn('expected_mode="700"', script)
        self.assertIn("os.fsync(fd)", script)
        self.assertIn("os.fsync(directory_fd)", script)
        self.assertIn("os.unlink(probe)", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

        python_probe = script.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
        compile(python_probe, "claim2car-host-preflight-python-probe", "exec")


if __name__ == "__main__":
    unittest.main()
