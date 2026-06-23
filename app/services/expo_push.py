# app/services/expo_push.py
import aiohttp
import os
from typing import List, Optional

class ExpoPushService:
    """Service pour envoyer des notifications push via Expo"""
    
    EXPO_PUSH_API = "https://exp.host/--/api/v2/push/send"
    
    @staticmethod
    async def send_notification(
        expo_token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        sound: str = "default"
    ) -> dict:
        """
        Envoyer une notification push à un utilisateur
        Returns: {
            "success": bool,
            "ticket_id": str (optional),
            "error": str (optional)
        }
        """
        if not expo_token or not expo_token.startswith("ExponentPushToken"):
            return {"success": False, "error": "Invalid Expo push token"}
        
        message = {
            "to": expo_token,
            "title": title,
            "body": body,
            "sound": sound,
            "priority": "high",
        }
        
        if data:
            message["data"] = data
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ExpoPushService.EXPO_PUSH_API,
                    json=message,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("status") == "ok":
                        return {
                            "success": True,
                            "ticket_id": result.get("data", {}).get("id")
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("message", "Unknown error")
                        }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_bulk_notifications(
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[dict] = None,
        sound: str = "default"
    ) -> dict:
        """
        Envoyer des notifications push à plusieurs utilisateurs
        Returns: {
            "success": int,
            "failed": int,
            "errors": List[str]
        }
        """
        results = {"success": 0, "failed": 0, "errors": []}
        
        for token in tokens:
            result = await ExpoPushService.send_notification(
                expo_token=token,
                title=title,
                body=body,
                data=data,
                sound=sound
            )
            
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{token}: {result.get('error')}")
        
        return results