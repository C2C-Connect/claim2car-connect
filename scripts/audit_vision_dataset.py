#!/usr/bin/env python3
"""Audit YOLO damage datasets and enforce license permission before training."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
class DatasetAuditError(ValueError): pass
def load_registry(path:Path)->dict[str,Any]:
 try: data=json.loads(path.read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError) as exc: raise DatasetAuditError(f"REGISTRY_READ_ERROR: {exc}") from exc
 if data.get("schema_version")!="c2c-vision-dataset-registry-v1" or not isinstance(data.get("datasets"),dict): raise DatasetAuditError("INVALID_REGISTRY_SCHEMA")
 return data
def check_license(dataset:dict[str,Any],mode:str)->list[str]:
 issues=[]
 if dataset.get("permission_required") and dataset.get("authorization_status")!="approved": issues.append("SOURCE_PERMISSION_NOT_APPROVED")
 if mode=="commercial" and dataset.get("commercial_use_allowed") is not True: issues.append("COMMERCIAL_USE_NOT_AUTHORIZED")
 if dataset.get("commercial_use_allowed") is None: issues.append("LICENSE_STATUS_UNKNOWN")
 if dataset.get("license") in (None,"","unknown"): issues.append("LICENSE_UNKNOWN")
 return issues
def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with path.open("rb") as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b""): h.update(chunk)
 return h.hexdigest()
def audit_dataset(dataset_id:str,dataset:dict[str,Any],root:Path,mode:str="commercial")->dict[str,Any]:
 if mode not in {"commercial","research"}: raise DatasetAuditError("INVALID_AUDIT_MODE")
 issues=check_license(dataset,mode)
 if dataset.get("format")!="yolo-detection":
  issues.append("UNSUPPORTED_FORMAT_FOR_THIS_AUDITOR")
  return {"dataset_id":dataset_id,"mode":mode,"audit_passed":False,"issues":issues}
 image_dir=root/dataset.get("image_dir","images");label_dir=root/dataset.get("label_dir","labels")
 extensions={".jpg",".jpeg",".png",".webp"}
 images=sorted(p for p in image_dir.rglob("*") if p.is_file() and p.suffix.lower() in extensions) if image_dir.exists() else []
 labels=sorted(label_dir.rglob("*.txt")) if label_dir.exists() else []
 if not images: issues.append("NO_IMAGES_FOUND")
 if not label_dir.exists(): issues.append("LABEL_DIRECTORY_MISSING")
 classes=dataset.get("classes") or []
 counts={name:0 for name in classes}; negatives=0;invalid=[];file_rows=[];hash_map={}
 image_keys={p.relative_to(image_dir).with_suffix("") for p in images} if image_dir.exists() else set()
 label_keys={p.relative_to(label_dir).with_suffix("") for p in labels} if label_dir.exists() else set()
 missing=image_keys-label_keys;orphan=label_keys-image_keys
 if missing: issues.append("IMAGE_LABEL_PAIRS_MISSING")
 if orphan: issues.append("ORPHAN_LABEL_FILES")
 for image in images:
  digest=sha256_file(image);relative=str(image.relative_to(root))
  if digest in hash_map: issues.append("DUPLICATE_IMAGE_CONTENT");hash_map[digest].append(relative)
  else: hash_map[digest]=[relative]
  file_rows.append((relative,digest))
  label=label_dir/(image.relative_to(image_dir).with_suffix(".txt"))
  if not label.exists(): continue
  file_rows.append((str(label.relative_to(root)),sha256_file(label)))
  lines=label.read_text(encoding="utf-8").splitlines()
  if not any(line.strip() for line in lines): negatives+=1;continue
  for number,line in enumerate(lines,1):
   if not line.strip(): continue
   parts=line.split()
   if len(parts)!=5: invalid.append(f"{label.relative_to(root)}:{number}:EXPECTED_5_COLUMNS");continue
   try: class_id=int(parts[0]);x,y,w,h=map(float,parts[1:])
   except ValueError: invalid.append(f"{label.relative_to(root)}:{number}:NON_NUMERIC");continue
   if class_id<0 or class_id>=len(classes): invalid.append(f"{label.relative_to(root)}:{number}:CLASS_ID_OUT_OF_RANGE");continue
   if not all(0<=v<=1 for v in (x,y,w,h)) or w<=0 or h<=0 or x-w/2<0 or y-h/2<0 or x+w/2>1 or y+h/2>1:
    invalid.append(f"{label.relative_to(root)}:{number}:INVALID_NORMALIZED_BOX");continue
   counts[classes[class_id]]+=1
 if invalid: issues.append("INVALID_LABEL_ROWS")
 manifest_text="\n".join(f"{path}:{digest}" for path,digest in sorted(file_rows))
 manifest_digest=hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
 return {"dataset_id":dataset_id,"display_name":dataset.get("display_name"),"version":dataset.get("version"),"license":dataset.get("license"),
  "commercial_use_allowed":dataset.get("commercial_use_allowed"),"attribution_required":dataset.get("attribution_required"),"mode":mode,
  "image_count":len(images),"label_file_count":len(labels),"negative_images":negatives,"class_counts":counts,
  "missing_label_count":len(missing),"orphan_label_count":len(orphan),"invalid_label_count":len(invalid),
  "duplicate_image_count":sum(len(v)-1 for v in hash_map.values() if len(v)>1),"manifest_sha256":manifest_digest,
  "issues":sorted(set(issues)),"invalid_rows":invalid[:100],"audit_passed":not issues and not invalid}
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--registry",type=Path,default=Path("config/vision_datasets.json"));p.add_argument("--dataset-id",required=True);p.add_argument("--root",type=Path,required=True);p.add_argument("--mode",choices=("commercial","research"),default="commercial");p.add_argument("--output",type=Path);args=p.parse_args()
 registry=load_registry(args.registry);dataset=registry["datasets"].get(args.dataset_id)
 if dataset is None: print(json.dumps({"error":"UNKNOWN_DATASET_ID","dataset_id":args.dataset_id}));return 2
 report=audit_dataset(args.dataset_id,dataset,args.root,args.mode);text=json.dumps(report,indent=2,sort_keys=True)
 if args.output: args.output.write_text(text+"\n",encoding="utf-8")
 print(text);return 0 if report["audit_passed"] else 2
if __name__=="__main__":raise SystemExit(main())
