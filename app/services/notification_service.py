# app/services/notification_service.py
import logging

logger = logging.getLogger("kemtchop.notifications")


class NotificationService:
    """
    🔔 Service de notifications (stub temporaire).
    À implémenter avec Firebase/Expo Push quand prêt.
    """

    @staticmethod
    async def notify_order_created(order_id: str, customer_name: str):
        """Notifie l'admin/cuisine d'une nouvelle commande"""
        logger.info(f"🔔 [STUB] Nouvelle commande {order_id} passée par {customer_name}")

    @staticmethod
    async def notify_offer_confirmed(offer_id: str, product_name: str):
        """Notifie tous les participants que le seuil est atteint et la production confirmée"""
        logger.info(f"🔔 [STUB] Offre CONFIRMÉE pour {product_name} (ID: {offer_id}). La production est lancée !")

    @staticmethod
    async def notify_production_status_change(offer_id: str, product_name: str, new_status: str):
        """Notifie les clients du changement d'état (COOKING, DELIVERING, etc.)"""
        logger.info(f"🔔 [STUB] Statut mis à jour pour {product_name} : {new_status}")
