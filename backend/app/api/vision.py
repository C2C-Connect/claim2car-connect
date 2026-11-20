"""Real-photo intake with a disclosed, non-AI contrast baseline."""
from __future__ import annotations
import hashlib, io
from typing import Any
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, require_implemented_protocol
from app.damage_localization import DamageLocalizationError, DamageObservationAdapter, HeuristicDamageDetector, zone_for_slot
from backend.app.security import require_internal_service
router=APIRouter(prefix="/api/v1/vision",tags=["vision"])
MAX_IMAGE_BYTES=10*1024*1024
ALLOWED_FORMATS={"JPEG","PNG","WEBP"}
_detector=HeuristicDamageDetector()
_observation_adapter=DamageObservationAdapter()
@router.post("/localize",dependencies=[Depends(require_internal_service)])
async def localize_photo(session_id:str=Query(...,min_length=1,max_length=128),slot:str=Query(...,min_length=1,max_length=64),protocol_version:str=Query(DEFAULT_CAPTURE_PROTOCOL),file:UploadFile=File(...))->dict[str,Any]:
    if not session_id.strip(): raise HTTPException(422,detail={"code":"INVALID_SESSION_ID"})
    try: protocol=require_implemented_protocol(protocol_version)
    except ValueError as exc: raise HTTPException(422,detail={"code":str(exc)}) from exc
    if slot not in protocol.slots: raise HTTPException(422,detail={"code":"INVALID_CAPTURE_SLOT"})
    if zone_for_slot(slot,protocol_version) is None: raise HTTPException(422,detail={"code":"LOCALIZATION_REQUIRES_EXTERIOR_SLOT"})
    raw=await file.read(MAX_IMAGE_BYTES+1)
    if len(raw)>MAX_IMAGE_BYTES: raise HTTPException(413,detail={"code":"IMAGE_TOO_LARGE"})
    if not raw: raise HTTPException(400,detail={"code":"EMPTY_IMAGE"})
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image_format=(image.format or "").upper()
            if image_format not in ALLOWED_FORMATS: raise HTTPException(415,detail={"code":"UNSUPPORTED_IMAGE_FORMAT"})
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width,height=image.size
            if width<32 or height<32: raise HTTPException(422,detail={"code":"IMAGE_DIMENSIONS_TOO_SMALL"})
            gray=image.convert("L").resize((64,64),Image.Resampling.LANCZOS)
            data=list(gray.getdata())
            pixels=[data[y*64:(y+1)*64] for y in range(64)]
    except HTTPException: raise
    except (UnidentifiedImageError,OSError,ValueError) as exc: raise HTTPException(400,detail={"code":"INVALID_IMAGE"}) from exc
    digest=hashlib.sha256(raw).hexdigest()
    try:
        regions=_detector.detect(slot,pixels,protocol_version=protocol_version)
        observations=[_observation_adapter.to_observation(r).__dict__ for r in regions]
    except DamageLocalizationError as exc: raise HTTPException(422,detail={"code":exc.code}) from exc
    return {"session_id":session_id,"capture_slot":slot,"capture_protocol":protocol_version,
      "image":{"sha256":digest,"byte_length":len(raw),"format":image_format,"width":width,"height":height,"persisted":False},
      "analysis":{"method":"heuristic_contrast_baseline","model_status":"BASELINE_NOT_AI","model_version":_detector.model_version,
      "trained_model_inference":False,"appraisal":False,"physical_measurements":False,"observations":observations,
      "note":"Image-space contrast candidates only; not damage confirmation, severity, depth, safety, repair scope, or estimate."}}
