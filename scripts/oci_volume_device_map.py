#!/usr/bin/env python3
"""Fail-closed mapping of OCI paravirtualized volume OCIDs to guest block devices.
This read-only tool never formats, partitions, encrypts, mounts, or writes a device.
"""
from __future__ import annotations
import argparse,json,os,stat,subprocess,sys
from collections.abc import Callable,Iterable
from pathlib import Path
from typing import Any
class MappingError(ValueError): """OCI attachment identity is ambiguous or unproven."""
def _is_block_device(path:str)->bool:
 try:return stat.S_ISBLK(os.stat(path).st_mode)
 except OSError:return False
def resolve_volume_devices(attachments:Iterable[dict[str,Any]],postgres_volume_id:str,evidence_volume_id:str,*,block_device_probe:Callable[[str],bool]=_is_block_device,canonicalize:Callable[[str],str]=os.path.realpath)->dict[str,dict[str,str]]:
 if not postgres_volume_id or not evidence_volume_id or postgres_volume_id==evidence_volume_id:raise MappingError("EXPECTED_VOLUME_OCIDS_INVALID")
 expected={postgres_volume_id:"postgres",evidence_volume_id:"evidence"}; matches={x:[] for x in expected}
 for item in attachments:
  if not isinstance(item,dict):raise MappingError("ATTACHMENT_RECORD_INVALID")
  if item.get("volumeId") in matches:matches[item["volumeId"]].append(item)
 resolved={}; used=set()
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
def _oci_attachments(instance_id):
 result=subprocess.run(["oci","compute","volume-attachment","list","--instance-id",instance_id,"--all","--output","json"],check=True,capture_output=True,text=True,timeout=60)
 data=json.loads(result.stdout)
 if not isinstance(data,dict) or not isinstance(data.get("data"),list):raise MappingError("OCI_ATTACHMENT_RESPONSE_INVALID")
 return data["data"]
def write_json_secure(path,document):
 target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
 temp=target.with_suffix(target.suffix+".tmp");temp.write_text(json.dumps(document,indent=2,sort_keys=True)+"\n")
 os.chmod(temp,0o600);temp.replace(target)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--instance-id",required=True);p.add_argument("--postgres-volume-id",required=True);p.add_argument("--evidence-volume-id",required=True);p.add_argument("--json-output")
 a=p.parse_args()
 try:
  data=resolve_volume_devices(_oci_attachments(a.instance_id),a.postgres_volume_id,a.evidence_volume_id)
  if a.json_output:write_json_secure(a.json_output,data)
 except (OSError,subprocess.SubprocessError,json.JSONDecodeError,MappingError) as e:
  print(f"FAIL OCI_VOLUME_IDENTITY:{type(e).__name__}:{e}",file=sys.stderr);return 2
 print(json.dumps(data,indent=2,sort_keys=True))
 if a.json_output:print("Machine-readable mapping saved with mode 0600 to",a.json_output)
 print("PASS: distinct OCI volume OCIDs map to attached guest block devices; read-only.")
 return 0
if __name__=="__main__":raise SystemExit(main())
