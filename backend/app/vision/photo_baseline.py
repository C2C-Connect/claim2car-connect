"""In-memory image-space localization using a deterministic contrast baseline; not AI/appraisal."""
from __future__ import annotations
import hashlib,io
from typing import Any
from PIL import Image,UnidentifiedImageError
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL,require_implemented_protocol
from app.damage_localization import DamageLocalizationError,DamageObservationAdapter,HeuristicDamageDetector,zone_for_slot
MAX_IMAGE_BYTES=10*1024*1024
MAX_IMAGE_PIXELS=25_000_000
ALLOWED_FORMATS={"JPEG","PNG","WEBP"}
class PhotoBaselineError(ValueError):
 def __init__(self,code:str,status_code:int=400):
  super().__init__(code);self.code=code;self.status_code=status_code
_detector=HeuristicDamageDetector();_adapter=DamageObservationAdapter()
def analyze_photo_bytes(raw:bytes,slot:str,protocol_version:str=DEFAULT_CAPTURE_PROTOCOL)->dict[str,Any]:
 if not isinstance(raw,bytes) or not raw: raise PhotoBaselineError("EMPTY_IMAGE",400)
 if len(raw)>MAX_IMAGE_BYTES: raise PhotoBaselineError("IMAGE_TOO_LARGE",413)
 try: protocol=require_implemented_protocol(protocol_version)
 except ValueError as exc: raise PhotoBaselineError(str(exc),422) from exc
 if slot not in protocol.slots: raise PhotoBaselineError("INVALID_CAPTURE_SLOT",422)
 if zone_for_slot(slot,protocol_version) is None: raise PhotoBaselineError("LOCALIZATION_REQUIRES_EXTERIOR_SLOT",422)
 try:
  with Image.open(io.BytesIO(raw)) as im:
   fmt=(im.format or "").upper()
   if fmt not in ALLOWED_FORMATS: raise PhotoBaselineError("UNSUPPORTED_IMAGE_FORMAT",415)
   im.verify()
  with Image.open(io.BytesIO(raw)) as im:
   width,height=im.size
   if width*height>MAX_IMAGE_PIXELS: raise PhotoBaselineError("IMAGE_PIXEL_LIMIT_EXCEEDED",413)
   if width<32 or height<32: raise PhotoBaselineError("IMAGE_DIMENSIONS_TOO_SMALL",422)
   gray=im.convert("L").resize((64,64),Image.Resampling.LANCZOS)
   data=list(gray.getdata());pixels=[data[y*64:(y+1)*64] for y in range(64)]
 except PhotoBaselineError: raise
 except (UnidentifiedImageError,OSError,ValueError) as exc: raise PhotoBaselineError("INVALID_IMAGE",400) from exc
 try:
  regions=_detector.detect(slot,pixels,protocol_version=protocol_version)
  observations=[_adapter.to_observation(r).__dict__ for r in regions]
 except DamageLocalizationError as exc: raise PhotoBaselineError(exc.code,422) from exc
 return {"image":{"sha256":hashlib.sha256(raw).hexdigest(),"byte_length":len(raw),"format":fmt,"width":width,"height":height},
 "analysis":{"status":"COMPLETED","method":"heuristic_contrast_baseline","model_status":"BASELINE_NOT_AI","model_version":_detector.model_version,
 "trained_model_inference":False,"appraisal":False,"physical_measurements":False,"observations":observations,
 "note":"Image-space contrast candidates only; not damage confirmation, severity, depth, safety, repair scope, or estimate."}}
