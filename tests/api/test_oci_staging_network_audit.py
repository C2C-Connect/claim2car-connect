import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "oci_staging_network_audit.py"
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

    def test_returned_security_list_ids_must_match_subnet_inventory(self):
        documents = [{"data": {
            "id": "sl-unattached",
            "displayName": "unattached",
            "ingressSecurityRules": [],
        }}]
        findings = AUDIT.audit_network(self.subnet, documents, "vcn-good")
        self.assertIn("SECURITY_LIST_ID_MISMATCH:unattached", findings)
        self.assertIn("SECURITY_LIST_IDS_UNVERIFIED:sl-1", findings)

    def test_duplicate_security_list_ids_in_subnet_fail_closed(self):
        subnet = {"data": {
            "vcnId": "vcn-good",
            "prohibitPublicIpOnVnic": True,
            "securityListIds": ["sl-1", "sl-1"],
        }}
        findings = AUDIT.audit_network(subnet, [{"data": {"id": "sl-1", "ingressSecurityRules": []}}], "vcn-good")
        self.assertIn("SUBNET_SECURITY_LIST_IDS_INVALID", findings)

    def test_duplicate_returned_list_identity_fails_and_rules_still_checked(self):
        docs = [
            {"data": {"id": "sl-1", "displayName": "first", "ingressSecurityRules": []}},
            {"data": {"id": "sl-1", "displayName": "duplicate", "ingressSecurityRules": [
                {"protocol": "all", "source": "::/0"}
            ]}},
        ]
        subnet = {"data": {"vcnId": "vcn-good", "prohibitPublicIpOnVnic": True, "securityListIds": ["sl-1", "sl-2"]}}
        findings = AUDIT.audit_network(subnet, docs, "vcn-good")
        self.assertIn("SECURITY_LIST_ID_MISMATCH:duplicate", findings)
        self.assertIn("SECURITY_LIST_IDS_UNVERIFIED:sl-2", findings)
        self.assertTrue(any(item.startswith("PUBLIC_INGRESS:duplicate:0") for item in findings))

    def test_manual_github_network_audit_workflow_is_read_only_and_fail_closed(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "oci-staging-network-audit.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("environment: oci-staging", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("oci-cli==3.96.3", workflow)
        self.assertIn("scripts/oci_staging_network_audit.py", workflow)
        self.assertIn("OCI_API_PRIVATE_KEY", workflow)
        self.assertIn("no network rule changes were made", workflow.lower())
        for forbidden in ("terraform apply", "oci network security-list update", "oci network security-list create", "oci network security-list delete"):
            self.assertNotIn(forbidden, workflow.lower())


if __name__ == "__main__":
    unittest.main()
