"""Internal authenticated endpoint for real-photo contrast-baseline localization."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter,Depends,File,HTTPException,Query,UploadFile
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL
from backend.app.vision.photo_baseline import MAX_IMAGE_BYTES,PhotoBaselineError,analyze_photo_bytes
from backend.app.security import require_internal_service
router=APIRouter(prefix="/api/v1/vision",tags=["vision"])
@router.post("/localize",dependencies=[Depends(require_internal_service)])
async def localize_photo(session_id:str=Query(...,min_length=1,max_length=128),slot:str=Query(...,min_length=1,max_length=64),protocol_version:str=Query(DEFAULT_CAPTURE_PROTOCOL),file:UploadFile=File(...))->dict[str,Any]:
 raw=await file.read(MAX_IMAGE_BYTES+1)
 try: result=analyze_photo_bytes(raw,slot,protocol_version)
 except PhotoBaselineError as exc: raise HTTPException(status_code=exc.status_code,detail={"code":exc.code}) from exc
 return {"session_id":session_id,"capture_slot":slot,"capture_protocol":protocol_version,**result}
