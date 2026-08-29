# app/enums.py
"""
🎯 Enums centralisés pour KemTchop - Réalignement strict Production Culinaire
"""

from enum import Enum
from typing import List


class ProductionStatus(str, Enum):
    """📊 Cycle de vie d'une offre quotidienne (Production culinaire)"""
    
    PROPOSED = "proposed"       # Suggestion affichée, en attente du seuil minimum
    CONFIRMED = "confirmed"     # Seuil atteint ! La production est déclenchée
    COOKING = "cooking"         # 🔥 En cours de cuisine
    DELIVERING = "delivering"   # 📦 En livraison / Prêt à récupérer
    COMPLETED = "completed"     # ✔️ Journée terminée / Épuisé
    CANCELLED = "cancelled"     # ❌ Seuil non atteint à l'heure limite

    @property
    def is_accepting_orders(self) -> bool:
        return self in [self.PROPOSED, self.CONFIRMED]

    @classmethod
    def get_transitions(cls, current: "ProductionStatus") -> List["ProductionStatus"]:
        transitions = {
            cls.PROPOSED: [cls.CONFIRMED, cls.CANCELLED],
            cls.CONFIRMED: [cls.COOKING, cls.CANCELLED],
            cls.COOKING: [cls.DELIVERING, cls.CANCELLED],
            cls.DELIVERING: [cls.COMPLETED, cls.CANCELLED],
            cls.COMPLETED: [],
            cls.CANCELLED: [],
        }
        return transitions.get(current, [])


class OrderStatus(str, Enum):
    """📦 Cycle de vie d'une commande client"""
    PENDING = "pending"
    PAID = "paid"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    
    @property
    def is_paid(self) -> bool:
        return self in [self.PAID, self.CONFIRMED, self.PREPARING, self.READY, 
                        self.OUT_FOR_DELIVERY, self.DELIVERED]


class UserRole(str, Enum):
    """👥 Rôles utilisateurs"""
    CUSTOMER = "customer"
    AFFILIATE = "affiliate"
    LIVREUR = "livreur"
    CUISINE = "cuisine"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    
    @property
    def hierarchy_level(self) -> int:
        levels = {
            self.CUSTOMER: 1,
            self.AFFILIATE: 2,
            self.LIVREUR: 3,
            self.CUISINE: 4,
            self.MANAGER: 5,
            self.ADMIN: 6,
            self.SUPER_ADMIN: 7,
        }
        return levels.get(self, 0)
    
    def can_access(self, resource_role: "UserRole") -> bool:
        return self.hierarchy_level >= resource_role.hierarchy_level
