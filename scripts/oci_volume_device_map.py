#!/usr/bin/env python3
"""Fail-closed mapping of OCI paravirtualized volume OCIDs to guest block devices.
This read-only tool never formats, partitions, encrypts, mounts, or writes a device.
"""
from __future__ import annotations
import argparse,json,os,stat,subprocess,sys
from collections.abc import Callable,Iterable
from pathlib import Path
from typing import Any
class MappingError(ValueError):
    """Raised when OCI attachment identity cannot be proven unambiguously."""
def _is_block_device(path:str)->bool:
    try:return stat.S_ISBLK(os.stat(path).st_mode)
    except OSError:return False
def resolve_volume_devices(attachments:Iterable[dict[str,Any]],postgres_volume_id:str,evidence_volume_id:str,*,block_device_probe:Callable[[str],bool]=_is_block_device,canonicalize:Callable[[str],str]=os.path.realpath)->dict[str,dict[str,str]]:
    if not postgres_volume_id or not evidence_volume_id or postgres_volume_id==evidence_volume_id:raise MappingError("EXPECTED_VOLUME_OCIDS_INVALID")
    expected={postgres_volume_id:"postgres",evidence_volume_id:"evidence"};matches={x:[] for x in expected}
    for item in attachments:
        if not isinstance(item,dict):raise MappingError("ATTACHMENT_RECORD_INVALID")
        if item.get("volumeId") in matches:matches[item["volumeId"]].append(item)
    resolved={};used=set()
    for volume_id,purpose in expected.items():
        candidates=matches[volume_id]
        if len(candidates)!=1:raise MappingError(f"VOLUME_ATTACHMENT_COUNT_INVALID:{purpose}")
        row=candidates[0]
        if row.get("lifecycleState")!="ATTACHED":raise MappingError(f"VOLUME_NOT_ATTACHED:{purpose}")
        if row.get("attachmentType")!="paravirtualized":raise MappingError(f"VOLUME_ATTACHMENT_TYPE_INVALID:{purpose}")
        device=row.get("device")
        if not isinstance(device,str) or not device.startswith("/dev/"):raise MappingError(f"VOLUME_DEVICE_PATH_INVALID:{purpose}")
        canonical=canonicalize(device)
        if not canonical.startswith("/dev/") or canonical in used:raise MappingError(f"VOLUME_DEVICE_PATH_COLLISION:{purpose}")
        if not block_device_probe(canonical):raise MappingError(f"VOLUME_DEVICE_NOT_PRESENT_BLOCK_DEVICE:{purpose}")
        used.add(canonical);resolved[purpose]={"volume_ocid":volume_id,"device":canonical}
    return resolved
def _oci_attachments(instance_id:str)->list[dict[str,Any]]:
    result=subprocess.run(["oci","compute","volume-attachment","list","--instance-id",instance_id,"--all","--output","json"],check=True,capture_output=True,text=True,timeout=60)
    document=json.loads(result.stdout)
    if not isinstance(document,dict) or not isinstance(document.get("data"),list):raise MappingError("OCI_ATTACHMENT_RESPONSE_INVALID")
    return document["data"]
def write_json_secure(path:str,document:Any)->None:
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink():raise MappingError("JSON_OUTPUT_SYMLINK_REJECTED")
    temp=target.with_suffix(target.suffix+".tmp");temp.write_text(json.dumps(document,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    os.chmod(temp,0o600);temp.replace(target)
def main()->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--instance-id",required=True);parser.add_argument("--postgres-volume-id",required=True);parser.add_argument("--evidence-volume-id",required=True);parser.add_argument("--json-output")
    args=parser.parse_args()
    try:
        result=resolve_volume_devices(_oci_attachments(args.instance_id),args.postgres_volume_id,args.evidence_volume_id)
        if args.json_output:write_json_secure(args.json_output,result)
    except (OSError,subprocess.SubprocessError,json.JSONDecodeError,MappingError) as error:
        print(f"FAIL OCI_VOLUME_IDENTITY:{type(error).__name__}:{error}",file=sys.stderr);return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    if args.json_output:print(f"Machine-readable mapping saved: {args.json_output}")
    print("PASS: distinct OCI volume OCIDs map to attached guest block devices; read-only.")
    return 0
if __name__=="__main__":raise SystemExit(main())
