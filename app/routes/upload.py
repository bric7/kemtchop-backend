# app/routes/upload.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.auth import check_permission
from app.services.cloudinary_service import CloudinaryService

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image")
async def upload_image_endpoint(
    file: UploadFile = File(...),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    """✅ Upload image vers Cloudinary"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Seules les images sont acceptées")

    content = await file.read()
    result = await CloudinaryService.upload_image(content, folder="kemtchop/products")

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Erreur upload Cloudinary"))

    return {"url": result["url"], "public_id": result["public_id"]}


@router.post("/video")
async def upload_video_endpoint(
    file: UploadFile = File(...),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    """✅ Upload vidéo vers Cloudinary"""
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Seules les vidéos sont acceptées")

    content = await file.read()
    result = await CloudinaryService.upload_video(content, folder="kemtchop/videos")

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Erreur upload Cloudinary"))

    return {"url": result["url"], "public_id": result["public_id"]}