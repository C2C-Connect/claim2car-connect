#!/usr/bin/env python3
"""Train a research detector from audited canonical YOLO labels; no pretrained weights."""
from __future__ import annotations
import argparse,hashlib,json,random
from pathlib import Path
from typing import Any

def parse_yolo_rows(text:str,width:int,height:int,canonical_to_dense:dict[int,int])->tuple[list[list[float]],list[int]]:
 boxes=[];labels=[]
 for row,line in enumerate(text.splitlines(),1):
  if not line.strip():continue
  parts=line.split()
  if len(parts)!=5:raise ValueError(f"INVALID_LABEL_ROW:{row}")
  cid=int(parts[0]);cx,cy,bw,bh=map(float,parts[1:])
  if cid not in canonical_to_dense:raise ValueError(f"UNMAPPED_CANONICAL_CLASS:{cid}")
  if not all(0<=v<=1 for v in (cx,cy,bw,bh)) or bw<=0 or bh<=0 or cx-bw/2<0 or cy-bh/2<0 or cx+bw/2>1 or cy+bh/2>1:raise ValueError(f"INVALID_BOX:{row}")
  boxes.append([(cx-bw/2)*width,(cy-bh/2)*height,(cx+bw/2)*width,(cy+bh/2)*height]);labels.append(canonical_to_dense[cid])
 return boxes,labels

def build_class_map(manifest:dict[str,Any],taxonomy:dict[str,Any])->dict[int,int]:
 counts=manifest.get("label_counts",{});canonical=taxonomy["canonical_damage_classes"]
 observed=[c["id"] for c in canonical if counts.get(c["key"],0)>0]
 if not observed:raise ValueError("NO_TRAINABLE_DAMAGE_CLASSES")
 return {canonical_id:dense_id for dense_id,canonical_id in enumerate(observed,1)}
def iou(a:list[float],b:list[float])->float:
 x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3]);inter=max(0,x2-x1)*max(0,y2-y1)
 aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]);bb=max(0,b[2]-b[0])*max(0,b[3]-b[1]);union=aa+bb-inter
 return inter/union if union else 0.0
def detection_metrics(preds:list[dict[str,Any]],targets:list[dict[str,Any]],classes:list[int],iou_threshold:float=.5,score_threshold:float=.5)->dict[str,Any]:
 result={}
 for cid in classes:
  tp=fp=fn=0
  for pred,target in zip(preds,targets):
   boxes=[b for b,l,s in zip(pred["boxes"],pred["labels"],pred["scores"]) if l==cid and s>=score_threshold]
   truth=[b for b,l in zip(target["boxes"],target["labels"]) if l==cid];matched=set()
   for box in boxes:
    best=max(((iou(box,g),idx) for idx,g in enumerate(truth) if idx not in matched),default=(0.0,-1))
    if best[0]>=iou_threshold:tp+=1;matched.add(best[1])
    else:fp+=1
   fn+=len(truth)-len(matched)
  pr=tp/(tp+fp) if tp+fp else 0.0;rc=tp/(tp+fn) if tp+fn else 0.0
  result[str(cid)]={"tp":tp,"fp":fp,"fn":fn,"precision":pr,"recall":rc,"f1":2*pr*rc/(pr+rc) if pr+rc else 0.0}
 return {"iou_threshold":iou_threshold,"score_threshold":score_threshold,"per_class":result}
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--registry",type=Path,default=Path("config/vision_datasets.json"));p.add_argument("--taxonomy",type=Path,default=Path("config/damage_taxonomy.json"));p.add_argument("--dataset-id",required=True);p.add_argument("--dataset-root",type=Path,required=True);p.add_argument("--normalized-labels",type=Path,required=True);p.add_argument("--normalization-manifest",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--epochs",type=int,default=20);p.add_argument("--batch-size",type=int,default=2);p.add_argument("--lr",type=float,default=.001);p.add_argument("--seed",type=int,default=42);p.add_argument("--val-ratio",type=float,default=.2);p.add_argument("--device",default="auto");a=p.parse_args()
 if a.epochs<1 or a.batch_size<1 or not .05<=a.val_ratio<=.5:raise SystemExit("INVALID_TRAINING_CONFIG")
 from audit_vision_dataset import audit_dataset,load_registry
 reg=load_registry(a.registry);ds=reg["datasets"].get(a.dataset_id)
 if ds is None:raise SystemExit("UNKNOWN_DATASET")
 audit=audit_dataset(a.dataset_id,ds,a.dataset_root,"commercial")
 if not audit["audit_passed"]:raise SystemExit("DATASET_AUDIT_FAILED:"+",".join(audit["issues"]))
 norm=json.loads(a.normalization_manifest.read_text(encoding="utf-8"))
 taxonomy=json.loads(a.taxonomy.read_text(encoding="utf-8"))
 if norm.get("dataset_id")!=a.dataset_id or norm.get("source_manifest_sha256")!=audit["manifest_sha256"] or norm.get("taxonomy_version")!=taxonomy["schema_version"]:raise SystemExit("NORMALIZATION_MANIFEST_MISMATCH")
 for entry in norm.get("files",[]):
  file=a.normalized_labels/entry["path"]
  if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest()!=entry["sha256"]:raise SystemExit("NORMALIZED_LABEL_HASH_MISMATCH")
 class_map=build_class_map(norm,taxonomy);classes=[taxonomy["canonical_damage_classes"][cid]["key"] for cid in sorted(class_map)]
 images=sorted(f for f in (a.dataset_root/ds["image_dir"]).rglob("*") if f.is_file() and f.suffix.lower() in {".jpg",".jpeg",".png",".webp"})
 if len(images)<2:raise SystemExit("INSUFFICIENT_IMAGES")
 rng=random.Random(a.seed);idx=list(range(len(images)));rng.shuffle(idx);nv=max(1,int(len(idx)*a.val_ratio));val=sorted(idx[:nv]);train=idx[nv:]
 if not train:raise SystemExit("EMPTY_TRAIN_SPLIT")
 try:
  import torch,numpy as np
  from torch.utils.data import DataLoader,Dataset
  from torchvision.models.detection import fasterrcnn_mobilenet_v3_large_fpn
 except ImportError as exc:raise SystemExit("INSTALL requirements-vision-training.txt") from exc
 from PIL import Image
 label_root=a.normalized_labels/"labels"
 class DS(Dataset):
  def __init__(self,ids):self.ids=ids
  def __len__(self):return len(self.ids)
  def __getitem__(self,k):
   idx=self.ids[k];image_path=images[idx]
   with Image.open(image_path) as im:im=im.convert("RGB");w,h=im.size;t=torch.from_numpy(np.array(im)).permute(2,0,1).float()/255
   lab=label_root/(image_path.relative_to(a.dataset_root/ds["image_dir"]).with_suffix(".txt"))
   boxes,labels=parse_yolo_rows(lab.read_text() if lab.exists() else "",w,h,class_map)
   return t,{"boxes":torch.tensor(boxes,dtype=torch.float32).reshape(-1,4),"labels":torch.tensor(labels,dtype=torch.int64)}
 def collate(batch):return tuple(zip(*batch))
 train_loader=DataLoader(DS(train),batch_size=a.batch_size,shuffle=True,collate_fn=collate);val_loader=DataLoader(DS(val),batch_size=a.batch_size,shuffle=False,collate_fn=collate)
 device=torch.device("cuda" if a.device=="auto" and torch.cuda.is_available() else ("cpu" if a.device=="auto" else a.device));torch.manual_seed(a.seed)
 model=fasterrcnn_mobilenet_v3_large_fpn(weights=None,weights_backbone=None,num_classes=len(classes)+1).to(device)
 opt=torch.optim.SGD([x for x in model.parameters() if x.requires_grad],lr=a.lr,momentum=.9,weight_decay=.0005);sched=torch.optim.lr_scheduler.StepLR(opt,max(1,a.epochs//3),gamma=.1);history=[]
 for ep in range(a.epochs):
  model.train();loss_total=0;steps=0
  for imgs,targets in train_loader:
   imgs=[x.to(device) for x in imgs];targets=[{k:v.to(device) for k,v in t.items()} for t in targets]
   loss=sum(model(imgs,targets).values());opt.zero_grad();loss.backward();opt.step();loss_total+=float(loss.detach());steps+=1
  sched.step();history.append({"epoch":ep+1,"mean_training_loss":loss_total/max(steps,1)})
 model.eval();preds=[];targs=[]
 with torch.no_grad():
  for imgs,targets in val_loader:
   out=model([x.to(device) for x in imgs]);preds.extend([{"boxes":x["boxes"].cpu().tolist(),"labels":x["labels"].cpu().tolist(),"scores":x["scores"].cpu().tolist()} for x in out]);targs.extend([{"boxes":x["boxes"].tolist(),"labels":x["labels"].tolist()} for x in targets])
 metrics=detection_metrics(preds,targs,list(range(1,len(classes)+1)))
 a.output.mkdir(parents=True,exist_ok=True);weight=a.output/"weights.pth";torch.save(model.state_dict(),weight)
 report={"model_type":"fasterrcnn_mobilenet_v3_large_fpn","weights_sha256":hashlib.sha256(weight.read_bytes()).hexdigest(),"dataset_id":a.dataset_id,"dataset_license":ds["license"],"commercial_use_allowed":ds["commercial_use_allowed"],"dataset_manifest_sha256":audit["manifest_sha256"],"normalization_manifest_sha256":norm["normalization_manifest_sha256"],"taxonomy_version":taxonomy["schema_version"],"classes":classes,"canonical_to_model_ids":class_map,"train_images":len(train),"validation_images":len(val),"validation_split":"random_holdout_from_source_dataset","synthetic_source_only":bool(ds.get("synthetic")),"real_world_validation":False,"production_eligible":False,"metrics":metrics,"training_history":history,"training_config":{"epochs":a.epochs,"batch_size":a.batch_size,"learning_rate":a.lr,"seed":a.seed,"device":str(device),"pretrained_weights_used":False}}
 (a.output/"model_card.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(report,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
