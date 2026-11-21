#!/usr/bin/env python3
"""Identity-checked OCI volume mount setup. Formatting requires explicit dual confirmation."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
from typing import Any
class MountSetupError(ValueError):pass
TARGETS={"postgres":"/var/lib/claim2car/postgres","evidence":"/var/lib/claim2car/evidence"}
def validate_mapping(mapping:Any,postgres_ocid:str,evidence_ocid:str)->dict[str,dict[str,str]]:
 if not isinstance(mapping,dict) or set(mapping)!=set(TARGETS):raise MountSetupError("MAPPING_PURPOSES_INVALID")
 if not postgres_ocid.startswith("ocid1.volume.") or not evidence_ocid.startswith("ocid1.volume.") or postgres_ocid==evidence_ocid:raise MountSetupError("EXPECTED_VOLUME_OCIDS_INVALID")
 out={};devices=set()
 for purpose,expected in (("postgres",postgres_ocid),("evidence",evidence_ocid)):
  row=mapping[purpose]
  if not isinstance(row,dict) or row.get("volume_ocid")!=expected:raise MountSetupError("VOLUME_OCID_MAPPING_MISMATCH:"+purpose)
  device=row.get("device")
  if not isinstance(device,str) or not device.startswith("/dev/") or ".." in device.split("/"):raise MountSetupError("DEVICE_PATH_INVALID:"+purpose)
  device=os.path.realpath(device)
  if device in devices:raise MountSetupError("DEVICE_COLLISION")
  devices.add(device);out[purpose]={"device":device,"volume_ocid":expected,"mountpoint":TARGETS[purpose]}
 return out
def format_confirmation(pg,evidence,enabled,confirm):
 expected=pg+","+evidence
 if enabled and confirm!=expected:raise MountSetupError("FORMAT_CONFIRMATION_MUST_MATCH_BOTH_VOLUME_OCIDS")
 if not enabled and confirm:raise MountSetupError("FORMAT_CONFIRMATION_WITHOUT_FORMAT_FLAG")
 return bool(enabled)
def run(cmd,*,check=True):
 p=subprocess.run(cmd,check=check,capture_output=True,text=True)
 return p
def fs_info(device):
 p=run(["blkid","-o","export",device],check=False)
 if p.returncode!=0:
  return None
 vals={}
 for line in p.stdout.splitlines():
  if "=" in line:
   k,v=line.split("=",1);vals[k]=v
 if not vals.get("TYPE") or not vals.get("UUID"):raise MountSetupError("FILESYSTEM_METADATA_INCOMPLETE:"+device)
 return vals
def check_unmounted(device):
 p=run(["findmnt","-rn","-S",device],check=False)
 if p.returncode==0 and p.stdout.strip():raise MountSetupError("DEVICE_ALREADY_MOUNTED:"+device)
def check_disk_without_partitions(device):
 rows=run(["lsblk","-nr","-o","TYPE",device]).stdout.splitlines()
 if rows!=["disk"]:raise MountSetupError("DEVICE_NOT_EMPTY_DISK_OR_HAS_PARTITIONS:"+device)
def check_no_signatures(device):
 out=run(["wipefs","--noheadings","--output","TYPE",device]).stdout.strip()
 if out:raise MountSetupError("DEVICE_HAS_EXISTING_SIGNATURES:"+device)
def existing_fstab(path,target,uuid):
 lines=path.read_text().splitlines() if path.exists() else []
 found=[]
 for line in lines:
  stripped=line.strip()
  if not stripped or stripped.startswith("#"):continue
  fields=stripped.split()
  if len(fields)>=3 and fields[1]==target:found.append(fields)
 if not found:return False
 if len(found)!=1 or found[0][0]!="UUID="+uuid or found[0][2]!="xfs":raise MountSetupError("FSTAB_TARGET_CONFLICT:"+target)
 return True
def append_fstab(entries,path="/etc/fstab"):
 f=Path(path);original=f.read_text() if f.exists() else ""
 additions=[]
 for uuid,target in entries:
  if existing_fstab(f,target,uuid):continue
  if any(line.split()[1:2]==[target] for line in original.splitlines() if line.strip() and not line.lstrip().startswith("#")):raise MountSetupError("FSTAB_TARGET_CONFLICT:"+target)
  additions.append(f"UUID={uuid} {target} xfs defaults,nofail 0 2")
 if not additions:return
 backup=f.with_suffix(f.suffix+".claim2car-backup")
 if f.exists() and not backup.exists():backup.write_text(original);os.chmod(backup,0o600)
 updated=original.rstrip()+"\n"+"\n".join(additions)+"\n"
 temp=f.with_suffix(f.suffix+".claim2car-tmp");temp.write_text(updated);os.chmod(temp,0o644);temp.replace(f)
def mounted_uuid(target):
 p=run(["findmnt","-rn","-o","UUID","--mountpoint",target],check=False)
 return p.stdout.strip() if p.returncode==0 else ""
def setup(mapping,*,format_empty=False,confirmation="",dry_run=False,fstab_path="/etc/fstab"):
 pg=mapping["postgres"]["volume_ocid"];ev=mapping["evidence"]["volume_ocid"]
 format_confirmation(pg,ev,format_empty,confirmation)
 plan=[];info={}
 for purpose,row in mapping.items():
  dev=row["device"];target=row["mountpoint"]
  if not os.path.exists(dev):raise MountSetupError("DEVICE_NOT_FOUND:"+dev)
  check_disk_without_partitions(dev)
  current=mounted_uuid(target)
  target_path=Path(target)
  if target_path.is_symlink():raise MountSetupError("MOUNTPOINT_SYMLINK_REJECTED:"+target)
  if target_path.exists() and not target_path.is_dir():raise MountSetupError("MOUNTPOINT_NOT_DIRECTORY:"+target)
  if current:
   fs=fs_info(dev)
   if not fs or fs["UUID"]!=current:raise MountSetupError("MOUNTPOINT_SOURCE_MISMATCH:"+target)
   if fs["TYPE"]!="xfs":raise MountSetupError("FILESYSTEM_TYPE_UNSUPPORTED:"+target)
   info[purpose]=fs;plan.append({"purpose":purpose,"action":"already-mounted","device":dev,"target":target,"uuid":fs["UUID"]});continue
  check_unmounted(dev)
  if target_path.exists() and any(target_path.iterdir()):raise MountSetupError("MOUNTPOINT_NOT_EMPTY:"+target)
  fs=fs_info(dev)
  if fs is None:
   check_no_signatures(dev)
   if not format_empty and not dry_run:raise MountSetupError("UNFORMATTED_VOLUME_REQUIRES_EXPLICIT_FORMAT:"+purpose)
   info[purpose]={"TYPE":"xfs","UUID":None};plan.append({"purpose":purpose,"action":"format-xfs-and-mount" if format_empty else "blank-requires-explicit-format","device":dev,"target":target})
  else:
   if fs["TYPE"]!="xfs":raise MountSetupError("FILESYSTEM_TYPE_UNSUPPORTED:"+purpose)
   info[purpose]=fs;plan.append({"purpose":purpose,"action":"mount-existing-xfs","device":dev,"target":target,"uuid":fs["UUID"]})
 if dry_run:return plan
 # Only after both devices pass identity, mount, partition, signature, and format-policy checks.
 for purpose,row in mapping.items():
  if info[purpose]["UUID"] is None:
   label="C2C_POSTGRES" if purpose=="postgres" else "C2C_EVIDENCE"
   run(["mkfs.xfs","-f","-L",label,row["device"]])
   info[purpose]=fs_info(row["device"])
  Path(row["mountpoint"]).mkdir(parents=True,exist_ok=True)
  if mounted_uuid(row["mountpoint"])!=info[purpose]["UUID"]:
   run(["mount","UUID="+info[purpose]["UUID"],row["mountpoint"]])
 entries=[(info[p]["UUID"],mapping[p]["mountpoint"]) for p in ("postgres","evidence")]
 append_fstab(entries,fstab_path)
 for purpose,row in mapping.items():
  target=Path(row["mountpoint"]);os.chown(target,10001,10001)
  os.chmod(target,0o750 if purpose=="postgres" else 0o700)
 if mounted_uuid(mapping["postgres"]["mountpoint"])==mounted_uuid(mapping["evidence"]["mountpoint"]):raise MountSetupError("PERSISTENT_VOLUME_UUID_COLLISION")
 return plan
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--mapping-json",required=True);p.add_argument("--postgres-volume-ocid",required=True);p.add_argument("--evidence-volume-ocid",required=True);p.add_argument("--format-empty",action="store_true");p.add_argument("--confirm-format-ocids",default="");p.add_argument("--dry-run",action="store_true")
 a=p.parse_args()
 try:
  mapping=validate_mapping(json.loads(Path(a.mapping_json).read_text()),a.postgres_volume_ocid,a.evidence_volume_ocid)
  plan=setup(mapping,format_empty=a.format_empty,confirmation=a.confirm_format_ocids,dry_run=a.dry_run)
 except (OSError,json.JSONDecodeError,subprocess.SubprocessError,MountSetupError) as e:
  print("FAIL OCI_VOLUME_MOUNT:"+str(e),file=sys.stderr);return 2
 print(json.dumps(plan,indent=2));print("PASS: volume mount preparation" if a.dry_run else "PASS: two distinct XFS volumes mounted by UUID and persisted in fstab")
 return 0
if __name__=="__main__":raise SystemExit(main())
