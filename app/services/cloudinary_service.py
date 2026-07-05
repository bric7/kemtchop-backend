# app/services/cloudinary_service.py
import asyncio
import os

import cloudinary
import cloudinary.uploader

# Configuration Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)


class CloudinaryService:
    """Service pour uploader et gérer les médias sur Cloudinary"""

    @staticmethod
    async def upload_image(file, folder: str = "kemtchop/products") -> dict:
        """
        Uploader une image sur Cloudinary (non-bloquant).
        Returns: {"success": bool, "url": str, "public_id": str, "width": int, "height": int}
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: cloudinary.uploader.upload(
                    file,
                    folder=folder,
                    resource_type="image",
                    transformation=[
                        {"quality": "auto:good"},
                        {"fetch_format": "auto"},
                    ],
                ),
            )
            return {
                "success": True,
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "width": result["width"],
                "height": result["height"],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def upload_video(file, folder: str = "kemtchop/videos") -> dict:
        """
        Uploader une vidéo sur Cloudinary (non-bloquant).
        Utilise eager_async=True pour supporter les vidéos > 10Mo.
        Returns: {"success": bool, "url": str, "public_id": str, "duration": float}
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: cloudinary.uploader.upload(
                    file,
                    folder=folder,
                    resource_type="video",
                    eager=[
                        {
                            "quality": "auto:good",
                            "fetch_format": "auto",
                        }
                    ],
                    eager_async=True,
                ),
            )
            return {
                "success": True,
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "duration": result.get("duration", 0),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def delete_resource(public_id: str, resource_type: str = "image") -> dict:
        """
        Supprimer un média de Cloudinary (non-bloquant).
        Returns: {"success": bool, "result": dict}
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: cloudinary.uploader.destroy(
                    public_id, resource_type=resource_type
                ),
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}