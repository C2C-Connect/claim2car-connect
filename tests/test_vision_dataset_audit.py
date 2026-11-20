from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("dataset_audit",ROOT/"scripts/audit_vision_dataset.py");mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def fixture(root):
 (root/"images").mkdir();(root/"labels_damage").mkdir()
 (root/"images/a.jpg").write_bytes(b"fixture-one");(root/"images/b.jpg").write_bytes(b"fixture-two")
 (root/"labels_damage/a.txt").write_text("0 0.5 0.5 0.2 0.2\n");(root/"labels_damage/b.txt").write_text("")
def test_syndcar_commercial_audit_passes_and_hashes_files(tmp_path):
 registry=mod.load_registry(ROOT/"config/vision_datasets.json");fixture(tmp_path)
 report=mod.audit_dataset("SYNDCAR-v1",registry["datasets"]["SYNDCAR-v1"],tmp_path,"commercial")
 assert report["audit_passed"] and report["image_count"]==2 and report["negative_images"]==1
 assert report["class_counts"]["broken_glass"]==1 and report["manifest_sha256"]
def test_cardd_blocks_without_permission_in_research_mode(tmp_path):
 registry=mod.load_registry(ROOT/"config/vision_datasets.json");fixture(tmp_path)
 report=mod.audit_dataset("CarDD",registry["datasets"]["CarDD"],tmp_path,"research")
 assert not report["audit_passed"] and "SOURCE_PERMISSION_NOT_APPROVED" in report["issues"]
def test_unknown_license_blocks_commercial_use(tmp_path):
 registry=mod.load_registry(ROOT/"config/vision_datasets.json")
 report=mod.audit_dataset("CrashCar101",registry["datasets"]["CrashCar101"],tmp_path,"commercial")
 assert not report["audit_passed"] and "LICENSE_UNKNOWN" in report["issues"]
def test_invalid_boxes_and_orphan_label_files_fail_audit(tmp_path):
 fixture(tmp_path);(tmp_path/"labels_damage/a.txt").write_text("0 0.5 0.5 2.0 0.2\n");(tmp_path/"labels_damage/orphan.txt").write_text("0 0.5 0.5 0.2 0.2\n")
 registry=mod.load_registry(ROOT/"config/vision_datasets.json");report=mod.audit_dataset("SYNDCAR-v1",registry["datasets"]["SYNDCAR-v1"],tmp_path,"commercial")
 assert not report["audit_passed"] and "INVALID_LABEL_ROWS" in report["issues"] and "ORPHAN_LABEL_FILES" in report["issues"]
