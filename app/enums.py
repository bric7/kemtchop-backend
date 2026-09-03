# app/enums.py
"""
🎯 Architecture Métier KemTchop v2.1 - La Séparation Production/Service
"""

from enum import Enum
from typing import List


class ProductionStatus(str, Enum):
    """📊 Cycle de vie d'une production culinaire (La Marmite) - KemTchop v3.0"""
    
    PROPOSED = "proposed"           # Suggestion initiale (Date >= J+1)
    RESERVATION = "reservation"     # Précommandes en cours (> 0 portions)
    CONFIRMED = "confirmed"         # Menu du Jour (Seuil atteint ou forcé)
    COOKING = "cooking"             # 🔥 En cours de préparation
    READY = "ready"                 # ✅ Prêt pour livraison
    DELIVERING = "delivering"       # 🚚 En route
    DELIVERED = "delivered"         # 🏁 Terminé
    CANCELLED = "cancelled"         # ❌ Annulé

    @property
    def is_accepting_orders(self) -> bool:
        """Loi de Vente KemTchop v3.0"""
        return self in [
            self.PROPOSED,
            self.RESERVATION,
            self.CONFIRMED,
            self.COOKING,
            self.READY
        ]

    @classmethod
    def get_transitions(cls, status: 'ProductionStatus') -> List['ProductionStatus']:
        """Définit les transitions autorisées dans la machine d'état KemTchop v3.0"""
        transitions = {
            cls.PROPOSED: [cls.RESERVATION, cls.CONFIRMED, cls.CANCELLED],
            cls.RESERVATION: [cls.CONFIRMED, cls.CANCELLED],
            cls.CONFIRMED: [cls.COOKING, cls.CANCELLED],
            cls.COOKING: [cls.READY, cls.CANCELLED],
            cls.READY: [cls.DELIVERING, cls.CANCELLED],
            cls.DELIVERING: [cls.DELIVERED, cls.CANCELLED],
            cls.DELIVERED: [],
            cls.CANCELLED: []
        }
        return transitions.get(status, [])


class OrderStatus(str, Enum):
    """📦 Cycle de vie d'une commande individuelle (Le Client)"""
    
    PENDING = "PENDING"             # Clic fait, en attente de paiement
    PAID = "PAID"                   # ✅ Acompte/Paiement reçu. Engagement client validé.
    PREPARING = "PREPARING"         # La marmite liée est en mode COOKING
    READY_TO_SHIP = "READY_TO_SHIP" # Le plat individuel est emballé
    SHIPPING = "SHIPPING"           # 🚚 Le livreur a pris cette commande précise
    DELIVERED = "DELIVERED"         # 😋 Remis au client
    CANCELLED = "CANCELLED"         # Annulation (remboursée ou non selon politique)
    
    @property
    def is_active(self) -> bool:
        return self not in [self.CANCELLED, self.DELIVERED]
