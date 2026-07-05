# app/routes/upload.py
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.auth import check_permission
from app.services.cloudinary_service import CloudinaryService

logger = logging.getLogger("kemtchop.upload")

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image")
async def upload_image_endpoint(
    file: UploadFile = File(...),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Seules les images sont acceptées")

    content = await file.read()
    logger.info(f"📤 Upload image: {file.filename} ({len(content)} bytes)")
    
    result = await CloudinaryService.upload_image(content, folder="kemtchop/products")

    if not result["success"]:
        logger.error(f"❌ Upload image ÉCHOUÉ: {result.get('error')}")
        raise HTTPException(status_code=500, detail=f"Cloudinary: {result.get('error')}")

    logger.info(f"✅ Image uploadée: {result['url']}")
    return {"url": result["url"], "public_id": result["public_id"]}


@router.post("/video")
async def upload_video_endpoint(
    file: UploadFile = File(...),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Seules les vidéos sont acceptées")

    content = await file.read()
    logger.info(f"📤 Upload video: {file.filename} ({len(content)} bytes)")
    
    result = await CloudinaryService.upload_video(content, folder="kemtchop/videos")

    if not result["success"]:
        logger.error(f"❌ Upload video ÉCHOUÉ: {result.get('error')}")
        raise HTTPException(status_code=500, detail=f"Cloudinary: {result.get('error')}")

    logger.info(f"✅ Vidéo uploadée: {result['url']}")
    return {"url": result["url"], "public_id": result["public_id"]}