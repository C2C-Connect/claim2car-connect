"""Tests for actual image bytes and contrast baseline disclosures."""
import hashlib,io
import pytest
from PIL import Image,ImageDraw
from app.vision.photo_baseline import PhotoBaselineError,analyze_photo_bytes
def make_image():
 im=Image.new("RGB",(128,128),(120,120,120));d=ImageDraw.Draw(im);d.rectangle((10,10,50,50),fill=(0,0,0));d.line((60,10,110,110),fill=(255,255,255),width=5);b=io.BytesIO();im.save(b,format="PNG");return b.getvalue()
def test_localization_hashes_actual_photo_and_marks_baseline():
 raw=make_image();r=analyze_photo_bytes(raw,"00_front_exterior")
 assert r["image"]["sha256"]==hashlib.sha256(raw).hexdigest()
 assert r["analysis"]["status"]=="COMPLETED" and r["analysis"]["model_status"]=="BASELINE_NOT_AI"
 assert r["analysis"]["trained_model_inference"] is False and r["analysis"]["physical_measurements"] is False
 assert r["analysis"]["method"]=="heuristic_contrast_baseline"
 assert all(len(o["bbox_normalized"])==4 for o in r["analysis"]["observations"])
def test_non_exterior_capture_view_rejected():
 with pytest.raises(PhotoBaselineError) as exc: analyze_photo_bytes(make_image(),"14_physical_vin")
 assert exc.value.code=="LOCALIZATION_REQUIRES_EXTERIOR_SLOT"
def test_corrupt_image_rejected():
 with pytest.raises(PhotoBaselineError) as exc: analyze_photo_bytes(b"bad","00_front_exterior")
 assert exc.value.code=="INVALID_IMAGE"
