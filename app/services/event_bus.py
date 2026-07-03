# app/services/event_bus.py
from typing import Dict, List, Callable, Any
from enum import Enum
import logging

logger = logging.getLogger("kemtchop.events")

class EventType(str, Enum):
    PRODUCTION_CONFIRMED = "production.confirmed"
    ORDER_PAID = "order.paid"
    PRODUCTION_READY = "production.ready"
    DELIVERY_ASSIGNED = "delivery.assigned"
    ORDER_CANCELLED = "order.cancelled"

class EventBus:
    """🔔 Bus d'événements pub/sub pour découplage des notifications"""
    
    _subscribers: Dict[EventType, List[Callable]] = {}
    
    @classmethod
    def subscribe(cls, event_type: EventType, handler: Callable[[Dict[str, Any]], None]):
        """Enregistrer un consommateur pour un type d'événement"""
        if event_type not in cls._subscribers:
            cls._subscribers[event_type] = []
        cls._subscribers[event_type].append(handler)
        logger.info("[EVENT] %s → nouveau subscriber: %s", event_type.value, handler.__name__)
    
    @classmethod
    def publish(cls, event_type: EventType, payload: Dict[str, Any]):
        """Publier un événement → tous les subscribers sont notifiés"""
        if event_type not in cls._subscribers:
            logger.warning("[EVENT] %s : aucun subscriber", event_type.value)
            return
        
        logger.info("[EVENT] 📢 %s publié avec %d clés", event_type.value, len(payload))
        
        for handler in cls._subscribers[event_type]:
            try:
                handler(payload)
                logger.debug("[EVENT] ✓ %s traité par %s", event_type.value, handler.__name__)
            except Exception as e:
                logger.error("[EVENT] ❌ %s échec dans %s : %s", event_type.value, handler.__name__, e)
                # ⚠️ Un handler qui plante n'arrête pas les autres

# 📦 Consommateurs exemple
def push_notification_handler(payload: Dict[str, Any]):
    """📱 Envoie une push notification Expo"""
    from app.services.expo_push import ExpoPushService
    ExpoPushService.send_to_menu_subscribers(
        menu_id=payload["menu_id"],
        title="Production confirmée ! 🎉",
        body=f"{payload['product_name']} est en cuisine pour demain",
        data={"type": "production_confirmed", "menu_id": payload["menu_id"]}
    )

def sms_handler(payload: Dict[str, Any]):
    """📞 Envoie un SMS aux clients prioritaires"""
    # Implémentation Twilio / Africa's Talking
    pass

def dashboard_ws_handler(payload: Dict[str, Any]):
    """🖥️ Met à jour le dashboard en temps réel via WebSocket"""
    from app.services.websocket_manager import manager
    manager.broadcast_to_hub(
        hub_id=payload.get("hub_id"),
        message={"type": "production_updated", "data": payload}
    )

# 🟢 Enregistrement au startup
EventBus.subscribe(EventType.PRODUCTION_CONFIRMED, push_notification_handler)
EventBus.subscribe(EventType.PRODUCTION_CONFIRMED, sms_handler)
EventBus.subscribe(EventType.PRODUCTION_CONFIRMED, dashboard_ws_handler)