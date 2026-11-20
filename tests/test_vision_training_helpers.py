from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location("train_helpers",ROOT/"scripts/train_damage_detector.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_yolo_box_conversion_dense_mapping():
 b,l=m.parse_yolo_rows("4 0.5 0.5 0.2 0.4\n1 0.25 0.25 0.1 0.1",100,200,{1:1,4:2})
 assert b==[[40.0,60.0,60.0,140.0],[20.0,40.0,30.0,60.0]] and l==[2,1]
def test_parser_rejects_unmapped_class_and_bad_bounds():
 for text,expected in [("9 0.5 0.5 0.2 0.2","UNMAPPED_CANONICAL_CLASS"),("1 0.5 0.5 2.0 0.2","INVALID_BOX")]:
  try:m.parse_yolo_rows(text,100,100,{1:1})
  except ValueError as exc:assert expected in str(exc)
  else:raise AssertionError("invalid labels accepted")
def test_metrics_at_iou_threshold():
 p=[{"boxes":[[0,0,10,10],[20,20,30,30]],"labels":[1,1],"scores":[.9,.6]}];t=[{"boxes":[[0,0,10,10]],"labels":[1]}]
 r=m.detection_metrics(p,t,[1]);assert r["per_class"]["1"]["tp"]==1 and r["per_class"]["1"]["fp"]==1 and r["per_class"]["1"]["fn"]==0
