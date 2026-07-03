# app/routes/websocket.py
from fastapi import APIRouter, WebSocket, Depends, Query

router = APIRouter()

@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    hub_id: int = Query(...),
    token: str = Query(...)  # JWT token pour auth
):
    # ✅ Vérification du token (simplifiée ici)
    from app.auth import verify_token_for_websocket
    user = verify_token_for_websocket(token)
    if not user or "dashboard" not in user.get("permissions", []):
        await websocket.close(code=4003)  # Forbidden
        return
    
    await manager.connect(websocket, str(hub_id))
    
    try:
        while True:
            # Le dashboard peut envoyer des commandes (optionnel)
            data = await websocket.receive_text()
            # ... traitement des commandes client ...
    except:
        manager.disconnect(websocket, str(hub_id))