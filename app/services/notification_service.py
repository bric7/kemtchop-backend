# app/services/notification_service.py
import logging

logger = logging.getLogger("kemtchop.notifications")


class NotificationService:
    """
    🔔 Service de notifications (stub temporaire).
    À implémenter avec Firebase/Expo Push quand prêt.
    """

    @staticmethod
    async def notify_order_confirmed(user_id: str, order_data: dict):
        logger.info(f"🔔 [STUB] Order confirmed notification for user {user_id}")

    @staticmethod
    async def notify_pot_funded(pot_id: str, product_name: str):
        logger.info(f"🔔 [STUB] Pot funded notification for {product_name}")

    @staticmethod
    async def notify_production_ready(pot_id: str, product_name: str):
        logger.info(f"🔔 [STUB] Production ready notification for {product_name}")