# app/services/websocket_manager.py
from fastapi import WebSocket
from typing import Dict, Set, List
import json

class WebSocketManager:
    """🔌 Gestion des connexions WebSocket pour dashboard temps réel"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # hub_id → websockets
    
    async def connect(self, websocket: WebSocket, hub_id: str):
        await websocket.accept()
        if hub_id not in self.active_connections:
            self.active_connections[hub_id] = set()
        self.active_connections[hub_id].add(websocket)
        logger.info("[WS] 🟢 Connexion dashboard pour hub %s", hub_id)
    
    def disconnect(self, websocket: WebSocket, hub_id: str):
        if hub_id in self.active_connections:
            self.active_connections[hub_id].discard(websocket)
            if not self.active_connections[hub_id]:
                del self.active_connections[hub_id]
        logger.info("[WS] 🔴 Déconnexion dashboard pour hub %s", hub_id)
    
    async def broadcast_to_hub(self, hub_id: str, message: dict):
        """Envoyer un message à tous les dashboards d'un hub"""
        if hub_id not in self.active_connections:
            return
        
        payload = json.dumps(message)
        disconnected = set()
        
        for websocket in self.active_connections[hub_id]:
            try:
                await websocket.send_text(payload)
            except:
                disconnected.add(websocket)
        
        # Nettoyer les connexions mortes
        for ws in disconnected:
            self.disconnect(ws, hub_id)
        
        logger.debug("[WS] 📡 Broadcast à %d connexions pour hub %s", 
                    len(self.active_connections.get(hub_id, [])), hub_id)

manager = WebSocketManager()