# app/services/cloudinary_service.py
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
from typing import Optional

# Configuration Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True  # Utiliser HTTPS
)

class CloudinaryService:
    """Service pour uploader et gérer les médias sur Cloudinary"""
    
    @staticmethod
    async def upload_image(file, folder: str = "kemtchop/products") -> dict:
        """
        Uploader une image sur Cloudinary
        Returns: {
            "success": bool,
            "url": str,
            "public_id": str,
            "error": str (optional)
        }
        """
        try:
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type="image",
                transformation=[
                    {"quality": "auto:good"},
                    {"fetch_format": "auto"}
                ]
            )
            
            return {
                "success": True,
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "width": result["width"],
                "height": result["height"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def upload_video(file, folder: str = "kemtchop/videos") -> dict:
        """
        Uploader une vidéo sur Cloudinary
        Returns: {
            "success": bool,
            "url": str,
            "public_id": str,
            "error": str (optional)
        }
        """
        try:
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type="video",
                transformation=[
                    {"quality": "auto:good"},
                    {"fetch_format": "auto"}
                ]
            )
            
            return {
                "success": True,
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "duration": result.get("duration", 0)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def delete_resource(public_id: str, resource_type: str = "image") -> dict:
        """Supprimer un média de Cloudinary"""
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}