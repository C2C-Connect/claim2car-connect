#!/usr/bin/env python3
"""Read-only preflight audit for the OCI subnet security lists used by C2C staging."""
from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
import sys
from typing import Any


def _data(document: dict[str, Any]) -> dict[str, Any]:
    value = document.get("data", document)
    if not isinstance(value, dict):
        raise ValueError("OCI_RESPONSE_DATA_INVALID")
    return value


def audit_network(subnet_document: dict[str, Any], security_list_documents: list[dict[str, Any]], expected_vcn_id: str) -> list[str]:
    """Return fail-closed findings; an empty list means the inspected ingress is acceptable."""
    subnet = _data(subnet_document)
    findings: list[str] = []
    if subnet.get("vcnId") != expected_vcn_id:
        findings.append("SUBNET_VCN_MISMATCH")
    if subnet.get("prohibitPublicIpOnVnic") is not True:
        findings.append("SUBNET_DOES_NOT_PROHIBIT_PUBLIC_IP")
    security_ids = subnet.get("securityListIds")
    if not isinstance(security_ids, list) or not security_ids:
        findings.append("SUBNET_SECURITY_LISTS_MISSING")
        return findings
    if any(not isinstance(item, str) or not item for item in security_ids) or len(set(security_ids)) != len(security_ids):
        findings.append("SUBNET_SECURITY_LIST_IDS_INVALID")
        return findings
    if len(security_list_documents) != len(security_ids):
        findings.append("SECURITY_LIST_RESPONSE_COUNT_MISMATCH")

    expected_ids = set(security_ids)
    seen_ids: set[str] = set()
    for document in security_list_documents:
        security_list = _data(document)
        security_id = security_list.get("id")
        name = str(security_list.get("displayName") or security_id or "unnamed")
        if not isinstance(security_id, str) or security_id not in expected_ids or security_id in seen_ids:
            findings.append(f"SECURITY_LIST_ID_MISMATCH:{name}")
        elif security_id:
            seen_ids.add(security_id)
        # Continue checking ingress even if the object identity is unexpected.
        rules = security_list.get("ingressSecurityRules")
        if not isinstance(rules, list):
            findings.append(f"INGRESS_RULES_INVALID:{name}")
            continue
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                findings.append(f"INGRESS_RULE_INVALID:{name}:{index}")
                continue
            source = rule.get("source")
            if not isinstance(source, str):
                findings.append(f"INGRESS_SOURCE_INVALID:{name}:{index}")
                continue
            try:
                network = ipaddress.ip_network(source, strict=False)
            except ValueError:
                findings.append(f"INGRESS_SOURCE_INVALID:{name}:{index}")
                continue
            if network.prefixlen == 0:
                protocol = str(rule.get("protocol", "all"))
                findings.append(f"PUBLIC_INGRESS:{name}:{index}:protocol={protocol}:source={network}")
    missing_ids = expected_ids - seen_ids
    if missing_ids:
        findings.append("SECURITY_LIST_IDS_UNVERIFIED:" + ",".join(sorted(missing_ids)))
    return findings



def audit_nsg(nsg_document: dict[str, Any], rules_document: dict[str, Any], expected_vcn_id: str) -> list[str]:
    """Audit one network security group and its ingress rules; unsupported sources fail closed."""
    nsg = _data(nsg_document)
    findings: list[str] = []
    nsg_id = nsg.get("id")
    name = str(nsg.get("displayName") or nsg_id or "unnamed")
    if nsg.get("vcnId") != expected_vcn_id:
        findings.append(f"NSG_VCN_MISMATCH:{name}")
    rules = rules_document.get("data", rules_document)
    if not isinstance(rules, list):
        findings.append(f"NSG_RULES_INVALID:{name}")
        return findings
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            findings.append(f"NSG_RULE_INVALID:{name}:{index}")
            continue
        if str(rule.get("direction", "")).upper() != "INGRESS":
            continue
        source_type = rule.get("sourceType")
        source = rule.get("source")
        if source_type != "CIDR_BLOCK" or not isinstance(source, str):
            findings.append(f"NSG_INGRESS_SOURCE_UNSUPPORTED:{name}:{index}")
            continue
        try:
            network = ipaddress.ip_network(source, strict=False)
        except ValueError:
            findings.append(f"NSG_INGRESS_SOURCE_INVALID:{name}:{index}")
            continue
        if network.prefixlen == 0:
            findings.append(f"NSG_PUBLIC_INGRESS:{name}:{index}:source={network}")
    return findings

def _oci_json(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["oci", *args, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("OCI_RESPONSE_INVALID")
    return value


def run_audit(subnet_id: str, expected_vcn_id: str, nsg_ids: list[str] | None = None) -> list[str]:
    subnet_document = _oci_json("network", "subnet", "get", "--subnet-id", subnet_id)
    subnet = _data(subnet_document)
    ids = subnet.get("securityListIds")
    documents = []
    if isinstance(ids, list) and ids:
        documents = [
            _oci_json("network", "security-list", "get", "--security-list-id", str(security_id))
            for security_id in ids
        ]
    findings = audit_network(subnet_document, documents, expected_vcn_id)
    for nsg_id in nsg_ids or []:
        nsg_document = _oci_json("network", "nsg", "get", "--network-security-group-id", nsg_id)
        rules_document = _oci_json("network", "nsg", "rules", "list", "--network-security-group-id", nsg_id)
        nsg_data = _data(nsg_document)
        if nsg_data.get("id") != nsg_id:
            findings.append("NSG_ID_MISMATCH:" + str(nsg_data.get("displayName") or nsg_data.get("id") or "unnamed"))
        findings.extend(audit_nsg(nsg_document, rules_document, expected_vcn_id))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subnet-id", required=True)
    parser.add_argument("--expected-vcn-id", required=True)
    parser.add_argument("--nsg-id", action="append", default=[], help="Optional NSG OCID to audit; may be repeated.")
    args = parser.parse_args()
    try:
        findings = run_audit(args.subnet_id, args.expected_vcn_id, args.nsg_id)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL OCI_NETWORK_AUDIT_ERROR:{type(error).__name__}:{error}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"FAIL {finding}")
        return 1
    print("PASS OCI subnet identity, private-IP policy, and all attached security-list ingress rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
