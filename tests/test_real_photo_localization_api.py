"""Tests for real-image intake and baseline disclosures."""
import io,sys
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.security import require_internal_service
app.dependency_overrides[require_internal_service]=lambda:"test-service"
client=TestClient(app)
def png():
 im=Image.new("RGB",(256,256),(130,130,130));d=ImageDraw.Draw(im);d.rectangle((40,40,90,100),fill=(5,5,5));d.line((120,20,220,220),fill=(255,255,255),width=12);b=io.BytesIO();im.save(b,format="PNG");return b.getvalue()
def test_real_photo_intake_and_baseline_disclosures():
 raw=png();r=client.post("/api/v1/vision/localize",params={"session_id":"session-123","slot":"00_front_exterior"},files={"file":("front.png",raw,"image/png")})
 assert r.status_code==200,r.text
 j=r.json();assert j["image"]["sha256"] and j["image"]["byte_length"]==len(raw) and j["image"]["persisted"] is False
 assert j["image"]["format"]=="PNG" and j["analysis"]["model_status"]=="BASELINE_NOT_AI"
 assert j["analysis"]["trained_model_inference"] is False and j["analysis"]["appraisal"] is False and j["analysis"]["physical_measurements"] is False
 assert j["analysis"]["method"]=="heuristic_contrast_baseline"
def test_rejects_non_exterior_slot():
 r=client.post("/api/v1/vision/localize",params={"session_id":"s","slot":"14_physical_vin"},files={"file":("a.png",png(),"image/png")})
 assert r.status_code==422 and r.json()["detail"]["code"]=="LOCALIZATION_REQUIRES_EXTERIOR_SLOT"
def test_rejects_corrupt_image():
 r=client.post("/api/v1/vision/localize",params={"session_id":"s","slot":"00_front_exterior"},files={"file":("a.png",b"garbage","image/png")})
 assert r.status_code==400 and r.json()["detail"]["code"]=="INVALID_IMAGE"
def test_rejects_unknown_protocol():
 r=client.post("/api/v1/vision/localize",params={"session_id":"s","slot":"00_front_exterior","protocol_version":"unknown-v99"},files={"file":("a.png",png(),"image/png")})
 assert r.status_code==422 and r.json()["detail"]["code"]=="UNSUPPORTED_CAPTURE_PROTOCOL"

def test_rejects_image_pixel_bomb():
    im=Image.new("RGB",(6000,6000),(10,10,10));b=io.BytesIO();im.save(b,format="PNG")
    r=client.post("/api/v1/vision/localize",params={"session_id":"s","slot":"00_front_exterior"},files={"file":("huge.png",b.getvalue(),"image/png")})
    assert r.status_code==413 and r.json()["detail"]["code"]=="IMAGE_PIXEL_LIMIT_EXCEEDED"
