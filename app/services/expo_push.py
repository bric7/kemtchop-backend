# app/services/expo_push.py
import httpx
import logging

logger = logging.getLogger("kemtchop")

EXPO_PUSH_API = "https://exp.host/--/api/v2/push/send"

class ExpoPushService:
    @staticmethod
    async def send_notification(
        expo_token: str,
        title: str,
        body: str,
        data: dict = None,
        sound: str = "default"
    ) -> dict:
        """Envoie une notification push via l'API Expo"""
        
        payload = {
            "to": expo_token,
            "title": title,
            "body": body,
            "sound": sound,
            "data": data or {},
            "priority": "high",
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(EXPO_PUSH_API, json=payload)
                result = response.json()
                
                if result.get("status") == "ok":
                    logger.info(f"✅ Notification envoyée à {expo_token[:10]}...")
                    return {"success": True, "id": result.get("id")}
                else:
                    logger.error(f"❌ Erreur Expo API: {result}")
                    return {"success": False, "error": result.get("message")}
                    
        except httpx.RequestError as e:
            logger.error(f"❌ Erreur réseau Expo: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_bulk_notifications(
        tokens: list[str],
        title: str,
        body: str,
        data: dict = None
    ) -> dict:
        """Envoie une notification à plusieurs tokens (batch de 100 max par appel Expo)"""
        
        results = {"success": 0, "failed": 0, "errors": []}
        
        # Expo limite à 100 tokens par appel
        for i in range(0, len(tokens), 100):
            batch = tokens[i:i+100]
            payload = {
                "to": batch,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
                "priority": "high",
            }
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(EXPO_PUSH_API, json=payload)
                    batch_results = response.json().get("data", [])
                    
                    for result in batch_results:
                        if result.get("status") == "ok":
                            results["success"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append({
                                "token": result.get("to", "unknown"),
                                "error": result.get("message")
                            })
                            
            except Exception as e:
                logger.error(f"❌ Erreur batch notifications: {e}")
                results["failed"] += len(batch)
                results["errors"].append({"error": str(e)})
        
        return results