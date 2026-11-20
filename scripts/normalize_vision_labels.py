"""Convert authorized YOLO damage labels to Claim2Car taxonomy; no image copying/training."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
from audit_vision_dataset import DatasetAuditError,audit_dataset,load_registry
def normalize_labels(dataset_id:str,dataset:dict[str,Any],taxonomy:dict[str,Any],root:Path,output:Path,mode:str="commercial")->dict[str,Any]:
 audit=audit_dataset(dataset_id,dataset,root,mode)
 if not audit["audit_passed"]: raise DatasetAuditError("DATASET_AUDIT_FAILED: "+",".join(audit["issues"]))
 names=dataset.get("classes",[]);mapping=taxonomy.get("dataset_mappings",{}).get(dataset_id)
 if not mapping:raise DatasetAuditError("NO_TAXONOMY_MAPPING_FOR_DATASET")
 canonical=taxonomy["canonical_damage_classes"];ids={c["key"]:c["id"] for c in canonical}
 if any(target not in ids for target in mapping.values()):raise DatasetAuditError("INVALID_CANONICAL_MAPPING")
 source_ids={i:ids[mapping[name]] for i,name in enumerate(names) if name in mapping}
 if len(source_ids)!=len(names):raise DatasetAuditError("SOURCE_CLASS_MAPPING_INCOMPLETE")
 labels=root/dataset.get("label_dir","labels");dest_root=output/"labels";dest_root.mkdir(parents=True,exist_ok=True)
 counts={c["key"]:0 for c in canonical};files=[]
 for label in sorted(labels.rglob("*.txt")):
  rel=label.relative_to(labels);dest=dest_root/rel;dest.parent.mkdir(parents=True,exist_ok=True);rows=[]
  for n,line in enumerate(label.read_text(encoding="utf-8").splitlines(),1):
   if not line.strip():continue
   parts=line.split()
   if len(parts)!=5:raise DatasetAuditError(f"INVALID_LABEL_ROW:{label}:{n}")
   source=int(parts[0])
   if source not in source_ids:raise DatasetAuditError(f"UNMAPPED_SOURCE_CLASS:{label}:{n}")
   target=source_ids[source];rows.append(str(target)+" "+" ".join(parts[1:]));counts[canonical[target]["key"]]+=1
  dest.write_text("\n".join(rows)+("\n" if rows else ""),encoding="utf-8")
  files.append({"path":str(dest.relative_to(output)),"sha256":hashlib.sha256(dest.read_bytes()).hexdigest()})
 manifest={"schema_version":"claim2car-label-normalization-v1","dataset_id":dataset_id,"dataset_version":dataset.get("version"),"source_license":dataset.get("license"),"mode":mode,"source_manifest_sha256":audit["manifest_sha256"],"taxonomy_version":taxonomy["schema_version"],"source_to_canonical":{name:mapping[name] for name in names},"canonical_classes":[c["key"] for c in canonical],"label_counts":counts,"files":files}
 manifest["normalization_manifest_sha256"]=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 output.mkdir(parents=True,exist_ok=True);(output/"normalization_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
 return manifest
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--registry",type=Path,default=Path("config/vision_datasets.json"));p.add_argument("--taxonomy",type=Path,default=Path("config/damage_taxonomy.json"));p.add_argument("--dataset-id",required=True);p.add_argument("--root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--mode",choices=("commercial","research"),default="commercial");a=p.parse_args()
 registry=load_registry(a.registry);dataset=registry["datasets"].get(a.dataset_id)
 if dataset is None:print(json.dumps({"error":"UNKNOWN_DATASET"}));return 2
 taxonomy=json.loads(a.taxonomy.read_text(encoding="utf-8"))
 try:result=normalize_labels(a.dataset_id,dataset,taxonomy,a.root,a.output,a.mode)
 except (DatasetAuditError,ValueError) as exc:print(json.dumps({"error":str(exc)}));return 2
 print(json.dumps(result,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
