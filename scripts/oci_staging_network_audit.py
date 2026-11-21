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
    if len(security_list_documents) != len(security_ids):
        findings.append("SECURITY_LIST_RESPONSE_COUNT_MISMATCH")
        return findings

    for document in security_list_documents:
        security_list = _data(document)
        name = str(security_list.get("displayName") or security_list.get("id") or "unnamed")
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


def run_audit(subnet_id: str, expected_vcn_id: str) -> list[str]:
    subnet_document = _oci_json("network", "subnet", "get", "--subnet-id", subnet_id)
    subnet = _data(subnet_document)
    ids = subnet.get("securityListIds")
    if not isinstance(ids, list) or not ids:
        return audit_network(subnet_document, [], expected_vcn_id)
    documents = [
        _oci_json("network", "security-list", "get", "--security-list-id", str(security_id))
        for security_id in ids
    ]
    return audit_network(subnet_document, documents, expected_vcn_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subnet-id", required=True)
    parser.add_argument("--expected-vcn-id", required=True)
    args = parser.parse_args()
    try:
        findings = run_audit(args.subnet_id, args.expected_vcn_id)
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
