# app/services/notification_service.py
import logging
from typing import List, Optional
from app.services.expo_push import ExpoPushService

logger = logging.getLogger("kemtchop.notifications")


class NotificationService:
    """
    🔔 Service de notifications KemTchop v3.0
    Gère les notifications push via Expo pour les changements d'état des commandes et offres.
    """

    @staticmethod
    async def notify_order_status_change(expo_token: str, order_id: str, new_status: str):
        """Notifie un client du changement de statut de sa commande"""
        if not expo_token:
            return

        status_messages = {
            "PAID": ("Paiement Reçu ✅", "Votre commande est confirmée ! Nous vous préviendrons quand elle passera en cuisine."),
            "PREPARING": ("👨‍🍳 En Cuisine", "Bonne nouvelle ! Le chef prépare votre plat avec soin."),
            "READY_TO_SHIP": ("✅ Prêt pour Livraison", "Votre plat est emballé et prêt à partir !"),
            "SHIPPING": ("🚚 En Route !", "Le livreur a récupéré votre commande. Préparez-vous à déguster !"),
            "DELIVERED": ("😋 Bon Appétit !", "Votre commande a été livrée. Merci de votre confiance !"),
            "CANCELLED": ("❌ Commande Annulée", "Votre commande a été annulée. Contactez le support pour plus d'infos."),
        }

        title, body = status_messages.get(new_status, ("Mise à jour Commande", f"Votre commande #{order_id[-8:]} est maintenant : {new_status}"))

        await ExpoPushService.send_notification(
            expo_token=expo_token,
            title=title,
            body=body,
            data={"type": "ORDER_STATUS", "order_id": str(order_id), "status": new_status}
        )

    @staticmethod
    async def notify_offer_confirmed(offer_id: str, product_name: str, tokens: List[str]):
        """Notifie tous les participants que le seuil est atteint et la production confirmée"""
        if not tokens:
            return

        await ExpoPushService.send_bulk_notifications(
            tokens=tokens,
            title="🚀 Production Confirmée !",
            body=f"C'est officiel : le seuil est atteint pour {product_name} ! On allume le feu. 🔥",
            data={"type": "OFFER_CONFIRMED", "offer_id": str(offer_id)}
        )

    @staticmethod
    async def notify_order_created(order_id: str, customer_name: str):
        """Notifie l'admin/cuisine d'une nouvelle commande (Stub pour l'instant)"""
        logger.info(f"🔔 Nouvelle commande {order_id} passée par {customer_name}")
