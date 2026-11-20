from pathlib import Path
import importlib.util,sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("normalizer",ROOT/"scripts/normalize_vision_labels.py");mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def make(root):
 (root/"images").mkdir();(root/"labels_damage").mkdir()
 (root/"images/a.jpg").write_bytes(b"img-a");(root/"images/b.jpg").write_bytes(b"img-b")
 (root/"labels_damage/a.txt").write_text("0 0.5 0.5 0.2 0.2\n3 0.4 0.4 0.1 0.1\n")
 (root/"labels_damage/b.txt").write_text("1 0.3 0.3 0.2 0.2\n")
def load():
 r=mod.load_registry(ROOT/"config/vision_datasets.json");t=json.loads((ROOT/"config/damage_taxonomy.json").read_text());return r["datasets"]["SYNDCAR-v1"],t
def test_source_labels_map_and_manifest_created(tmp_path):
 make(tmp_path);d,t=load();out=tmp_path/"normalized";r=mod.normalize_labels("SYNDCAR-v1",d,t,tmp_path,out)
 lines=(out/"labels/a.txt").read_text().splitlines()
 assert lines[0].startswith("3 ") and lines[1].startswith("1 ") and (out/"labels/b.txt").read_text().startswith("4 ")
 assert r["label_counts"]["glass_breakage"]==1 and r["label_counts"]["lamp_damage"]==1 and r["normalization_manifest_sha256"]
def test_cardd_is_blocked_without_authorization(tmp_path):
 make(tmp_path);r=mod.load_registry(ROOT/"config/vision_datasets.json");t=json.loads((ROOT/"config/damage_taxonomy.json").read_text())
 try:mod.normalize_labels("CarDD",r["datasets"]["CarDD"],t,tmp_path,tmp_path/"out","research")
 except mod.DatasetAuditError as exc:assert "DATASET_AUDIT_FAILED" in str(exc)
 else:raise AssertionError("license gate should block CarDD")
