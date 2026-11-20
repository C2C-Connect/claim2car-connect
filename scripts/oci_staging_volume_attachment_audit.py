#!/usr/bin/env python3
"""Read-only OCI attachment identity audit. No storage operations."""
import argparse,json,re,sys
from pathlib import Path
class AuditError(ValueError): pass
def audit(payload,instance_id,postgres_id,evidence_id):
    ids=(postgres_id,evidence_id)
    if any(not isinstance(x,str) or not x.startswith("ocid1.volume.") for x in ids) or postgres_id==evidence_id: raise AuditError("EXPECTED_VOLUME_IDS_INVALID")
    data=payload.get("data") if isinstance(payload,dict) else None
    if not isinstance(data,list): raise AuditError("ATTACHMENT_LIST_INVALID")
    expected={postgres_id:"postgres",evidence_id:"evidence"}; matches={x:[] for x in expected}
    for row in data:
        if not isinstance(row,dict): raise AuditError("ATTACHMENT_RECORD_INVALID")
        if row.get("volumeId") in matches: matches[row["volumeId"]].append(row)
    result={}; devices=set()
    for vol,purpose in expected.items():
        rows=matches[vol]
        if len(rows)!=1: raise AuditError("ATTACHMENT_COUNT_INVALID:"+purpose)
        row=rows[0]
        if row.get("lifecycleState")!="ATTACHED": raise AuditError("VOLUME_NOT_ATTACHED:"+purpose)
        if row.get("attachmentType")!="paravirtualized": raise AuditError("ATTACHMENT_TYPE_INVALID:"+purpose)
        device=row.get("device")
        if not isinstance(device,str) or not re.fullmatch(r"/dev/[A-Za-z0-9._/-]+",device): raise AuditError("DEVICE_PATH_INVALID:"+purpose)
        if device in devices: raise AuditError("DEVICE_COLLISION:"+purpose)
        devices.add(device); result[purpose]={"volume_ocid":vol,"device":device,"lifecycle_state":row["lifecycleState"],"attachment_type":row["attachmentType"]}
    return {"instance_ocid":instance_id,"attachments":result,"control_plane_verified":True,"guest_device_probe_performed":False}
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--input",required=True); p.add_argument("--instance-id",required=True); p.add_argument("--postgres-volume-id",required=True); p.add_argument("--evidence-volume-id",required=True); a=p.parse_args()
    try: x=audit(json.loads(Path(a.input).read_text()),a.instance_id,a.postgres_volume_id,a.evidence_volume_id)
    except (OSError,json.JSONDecodeError,AuditError) as e: print("FAIL OCI_ATTACHMENT_AUDIT:"+str(e),file=sys.stderr); return 2
    print(json.dumps(x,indent=2)); print("PASS: distinct expected paravirtualized attachments verified at OCI control plane only"); return 0
if __name__=="__main__": sys.exit(main())
