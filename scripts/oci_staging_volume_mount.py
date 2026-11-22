#!/usr/bin/env python3
"""Identity-checked OCI volume mount setup; blank-volume formatting is opt-in."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
class MountSetupError(ValueError):
    """Raised when a device, mount, filesystem, or confirmation is unsafe."""
TARGETS={"postgres":"/var/lib/claim2car/postgres","evidence":"/var/lib/claim2car/evidence"}
EXPECTED_FS="xfs"
def validate_mapping(mapping:Any,postgres_ocid:str,evidence_ocid:str)->dict[str,dict[str,str]]:
    if not isinstance(mapping,dict) or set(mapping)!=set(TARGETS):raise MountSetupError("MAPPING_PURPOSES_INVALID")
    if not postgres_ocid.startswith("ocid1.volume.") or not evidence_ocid.startswith("ocid1.volume.") or postgres_ocid==evidence_ocid:raise MountSetupError("EXPECTED_VOLUME_OCIDS_INVALID")
    result={};devices=set()
    for purpose,expected in (("postgres",postgres_ocid),("evidence",evidence_ocid)):
        row=mapping[purpose]
        if not isinstance(row,dict) or row.get("volume_ocid")!=expected:raise MountSetupError("VOLUME_OCID_MAPPING_MISMATCH:"+purpose)
        device=row.get("device")
        if not isinstance(device,str) or not device.startswith("/dev/") or ".." in device.split("/"):raise MountSetupError("DEVICE_PATH_INVALID:"+purpose)
        if Path(device).is_symlink():raise MountSetupError("DEVICE_SYMLINK_REJECTED:"+purpose)
        canonical=os.path.realpath(device)
        if not canonical.startswith("/dev/") or canonical in devices:raise MountSetupError("DEVICE_COLLISION")
        devices.add(canonical);result[purpose]={"device":canonical,"volume_ocid":expected,"mountpoint":TARGETS[purpose]}
    return result
def validate_format_confirmation(pg,evidence,format_empty,confirmation):
    expected=pg+","+evidence
    if format_empty and confirmation!=expected:raise MountSetupError("FORMAT_CONFIRMATION_MUST_MATCH_BOTH_VOLUME_OCIDS")
    if not format_empty and confirmation:raise MountSetupError("FORMAT_CONFIRMATION_WITHOUT_FORMAT_FLAG")
def run_command(args,*,check=True):return subprocess.run(args,check=check,capture_output=True,text=True)
def filesystem_info(device):
    result=run_command(["blkid","-o","export",device],check=False)
    if result.returncode==2 and not result.stdout.strip():return None
    if result.returncode!=0:raise MountSetupError("BLKID_FAILED:"+device+":"+str(result.returncode))
    info={}
    for line in result.stdout.splitlines():
        if "=" in line:
            key,value=line.split("=",1);info[key]=value
    if not info.get("TYPE") or not info.get("UUID"):raise MountSetupError("FILESYSTEM_METADATA_INCOMPLETE:"+device)
    return info
def verify_disk_has_no_partitions(device):
    types=run_command(["lsblk","-nr","-o","TYPE",device]).stdout.splitlines()
    if types!=["disk"]:raise MountSetupError("DEVICE_NOT_WHOLE_DISK_OR_HAS_PARTITIONS:"+device)
def verify_unmounted(device):
    result=run_command(["findmnt","-rn","-S",device],check=False)
    if result.returncode==0 and result.stdout.strip():raise MountSetupError("DEVICE_ALREADY_MOUNTED:"+device)
def verify_no_signatures(device):
    result=run_command(["wipefs","--noheadings","--output","TYPE",device])
    if result.stdout.strip():raise MountSetupError("DEVICE_HAS_SIGNATURES:"+device)
def mounted_uuid(target):
    result=run_command(["findmnt","-rn","-o","UUID","--mountpoint",target],check=False)
    return result.stdout.strip() if result.returncode==0 else ""
def fstab_rows(path):
    if path.is_symlink():raise MountSetupError("FSTAB_SYMLINK_REJECTED")
    if not path.exists():return []
    return [line.strip().split() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
def validate_fstab(path,uuid,target):
    rows=fstab_rows(path)
    target_rows=[row for row in rows if len(row)>=2 and row[1]==target]
    uuid_rows=[row for row in rows if len(row)>=1 and row[0]=="UUID=" + uuid]
    if len(target_rows)>1 or len(uuid_rows)>1:raise MountSetupError("FSTAB_DUPLICATE_ENTRY")
    for row in rows:
        if len(row)<3:raise MountSetupError("FSTAB_ENTRY_MALFORMED")
        source,mountpoint,fs=row[:3]
        if mountpoint==target:
            if source!="UUID="+uuid or fs!=EXPECTED_FS:raise MountSetupError("FSTAB_TARGET_CONFLICT:"+target)
            return True
        if source=="UUID="+uuid:raise MountSetupError("FSTAB_UUID_ALREADY_ASSIGNED:"+uuid)
    return False
def validate_target_fstab_unassigned(path,target):
    if any(len(row)>=2 and row[1]==target for row in fstab_rows(path)):
        raise MountSetupError("FSTAB_TARGET_CONFLICT:"+target)
def _fsync_directory(directory):
    fd=os.open(directory,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
    try:os.fsync(fd)
    finally:os.close(fd)
def persist_fstab(entries,path):
    original=path.read_text() if path.exists() else ""
    additions=[]
    for uuid,target in entries:
        if not validate_fstab(path,uuid,target):additions.append(f"UUID={uuid} {target} {EXPECTED_FS} defaults,nofail 0 2")
    if not additions:return
    backup=path.with_name(path.name+".claim2car-backup")
    if path.exists() and not backup.exists():
        shutil.copy2(path,backup);os.chmod(backup,0o600)
        with backup.open("rb") as saved:os.fsync(saved.fileno())
        _fsync_directory(path.parent)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,prefix=f".{path.name}.",delete=False) as tmp:
            temp=Path(tmp.name)
            tmp.write(original.rstrip()+"\n"+"\n".join(additions)+"\n")
            tmp.flush();os.fsync(tmp.fileno())
        os.chmod(temp,0o644)
        temp.replace(path)
        _fsync_directory(path.parent)
    finally:
        if temp is not None and temp.exists():temp.unlink()
def verify_target(target):
    if target.is_symlink():raise MountSetupError("MOUNTPOINT_SYMLINK_REJECTED:"+str(target))
    if target.exists() and not target.is_dir():raise MountSetupError("MOUNTPOINT_NOT_DIRECTORY:"+str(target))
    if target.exists() and not mounted_uuid(str(target)) and any(target.iterdir()):raise MountSetupError("MOUNTPOINT_NOT_EMPTY:"+str(target))
def setup_mounts(mapping,*,format_empty=False,confirmation="",dry_run=False,fstab_path="/etc/fstab"):
    validate_format_confirmation(mapping["postgres"]["volume_ocid"],mapping["evidence"]["volume_ocid"],format_empty,confirmation)
    fstab=Path(fstab_path);plan=[];filesystems={}
    # Both devices are preflighted before formatting or mounting.
    for purpose,row in mapping.items():
        dev=row["device"];target=Path(row["mountpoint"])
        if not os.path.exists(dev):raise MountSetupError("DEVICE_NOT_FOUND:"+dev)
        verify_disk_has_no_partitions(dev);verify_target(target)
        current=mounted_uuid(str(target))
        if current:
            info=filesystem_info(dev)
            if not info or info["UUID"]!=current:raise MountSetupError("MOUNTPOINT_SOURCE_MISMATCH:"+str(target))
            if info["TYPE"]!=EXPECTED_FS:raise MountSetupError("FILESYSTEM_TYPE_UNSUPPORTED:"+purpose)
            validate_fstab(fstab,info["UUID"],str(target));filesystems[purpose]=info
            plan.append({"purpose":purpose,"action":"already-mounted","uuid":info["UUID"],"target":str(target)});continue
        verify_unmounted(dev);info=filesystem_info(dev)
        if info is None:
            verify_no_signatures(dev)
            validate_target_fstab_unassigned(fstab,str(target))
            if not dry_run and not format_empty:raise MountSetupError("UNFORMATTED_VOLUME_REQUIRES_EXPLICIT_FORMAT:"+purpose)
            filesystems[purpose]=None
            plan.append({"purpose":purpose,"action":"format-and-mount" if format_empty else "blank-volume-format-gate-required","device":dev,"target":str(target)})
        else:
            if info["TYPE"]!=EXPECTED_FS:raise MountSetupError("FILESYSTEM_TYPE_UNSUPPORTED:"+purpose)
            validate_fstab(fstab,info["UUID"],str(target));filesystems[purpose]=info
            plan.append({"purpose":purpose,"action":"mount-existing-xfs","uuid":info["UUID"],"target":str(target)})
    if dry_run:return plan
    for purpose,row in mapping.items():
        fs=filesystems[purpose]
        if fs is None:
            label="C2C_POSTGRES" if purpose=="postgres" else "C2C_EVIDENCE"
            run_command(["mkfs.xfs","-f","-L",label,row["device"]]);fs=filesystem_info(row["device"])
            if not fs or fs["TYPE"]!=EXPECTED_FS:raise MountSetupError("FORMAT_VERIFICATION_FAILED:"+purpose)
            filesystems[purpose]=fs
        target=Path(row["mountpoint"]);target.mkdir(parents=True,exist_ok=True)
        if mounted_uuid(str(target))!=fs["UUID"]:run_command(["mount","UUID="+fs["UUID"],str(target)])
    persist_fstab([(filesystems[p]["UUID"],mapping[p]["mountpoint"]) for p in ("postgres","evidence")],fstab)
    for purpose,row in mapping.items():
        target=Path(row["mountpoint"]);os.chown(target,10001,10001);os.chmod(target,0o750 if purpose=="postgres" else 0o700)
    if mounted_uuid(mapping["postgres"]["mountpoint"])==mounted_uuid(mapping["evidence"]["mountpoint"]):raise MountSetupError("PERSISTENT_VOLUME_UUID_COLLISION")
    return plan
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--mapping-json",required=True);p.add_argument("--postgres-volume-ocid",required=True);p.add_argument("--evidence-volume-ocid",required=True);p.add_argument("--format-empty",action="store_true");p.add_argument("--confirm-format-ocids",default="");p.add_argument("--dry-run",action="store_true");a=p.parse_args()
    if os.geteuid()!=0:print("FAIL OCI_VOLUME_MOUNT:ROOT_REQUIRED",file=sys.stderr);return 2
    try:
        mapping=validate_mapping(json.loads(Path(a.mapping_json).read_text()),a.postgres_volume_ocid,a.evidence_volume_ocid)
        plan=setup_mounts(mapping,format_empty=a.format_empty,confirmation=a.confirm_format_ocids,dry_run=a.dry_run)
    except (OSError,json.JSONDecodeError,subprocess.SubprocessError,MountSetupError) as e:print("FAIL OCI_VOLUME_MOUNT:"+str(e),file=sys.stderr);return 2
    print(json.dumps(plan,indent=2));print("PASS: dry-run; no disk/mount state changed" if a.dry_run else "PASS: distinct XFS volumes mounted by UUID and persisted in fstab");return 0
if __name__=="__main__":raise SystemExit(main())
