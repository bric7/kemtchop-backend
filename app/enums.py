# app/enums.py
"""
🎯 Enums centralisés pour KemTchop
Évite les fautes de frappe, permet l'autocomplétion, et documente les états valides.
"""

from enum import Enum
from typing import List


class ProductionStatus(str, Enum):
    """📊 Cycle de vie d'une production (DailyMenu)"""
    
    DRAFT = "draft"
    PUBLISHED = "published"
    CONFIRMED = "confirmed"
    COOKING = "cooking"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    
    @property
    def is_accepting_orders(self) -> bool:
        return self in [self.PUBLISHED, self.CONFIRMED]
    
    @property
    def is_terminal(self) -> bool:
        return self in [self.DELIVERED, self.CANCELLED]
    
    @property
    def is_kitchen_active(self) -> bool:
        return self in [self.CONFIRMED, self.COOKING, self.READY]
    
    @classmethod
    def get_transitions(cls, current: "ProductionStatus") -> List["ProductionStatus"]:
        transitions = {
            cls.DRAFT: [cls.PUBLISHED, cls.CANCELLED],
            cls.PUBLISHED: [cls.CONFIRMED, cls.CANCELLED],
            cls.CONFIRMED: [cls.COOKING, cls.CANCELLED],
            cls.COOKING: [cls.READY, cls.CANCELLED],
            cls.READY: [cls.DELIVERED, cls.CANCELLED],
            cls.DELIVERED: [],
            cls.CANCELLED: [],
        }
        return transitions.get(current, [])


# app/enums.py
class CampaignStatus(str, Enum):
    ACTIVE = "active"           # À financer
    FUNDED = "funded"           # Production confirmée
    COOKING = "cooking"         # 🔥 Cuisson en cours
    DELIVERING = "delivering"   # 📦 En livraison
    DELIVERED = "delivered"     # ✔ Livré
    CANCELLED = "cancelled"     # ❌ Annulée
    EXPIRED = "expired"         # ⏰ Expirée

    @classmethod
    def get_transitions(cls, current_status: "CampaignStatus") -> list["CampaignStatus"]:
        """Définit les transitions valides entre états"""
        transitions = {
            cls.ACTIVE: [cls.FUNDED, cls.CANCELLED, cls.EXPIRED],
            cls.FUNDED: [cls.COOKING, cls.CANCELLED],
            cls.COOKING: [cls.DELIVERING, cls.CANCELLED],
            cls.DELIVERING: [cls.DELIVERED, cls.CANCELLED],
            cls.DELIVERED: [],
            cls.CANCELLED: [],
            cls.EXPIRED: [],
        }
        return transitions.get(current_status, [])

class CollectivePotStatus(str, Enum):
    ACTIVE = "active"           # À financer
    FUNDED = "funded"           # Production confirmée
    COOKING = "cooking"         # Cuisson en cours
    DELIVERING = "delivering"   # En livraison
    DELIVERED = "delivered"     # Livré
    CANCELLED = "cancelled"     # Annulée
    EXPIRED = "expired"         # Expirée

    @classmethod
    def get_transitions(cls, current_status: "CollectivePotStatus") -> list["CollectivePotStatus"]:
        transitions = {
            cls.ACTIVE: [cls.FUNDED, cls.CANCELLED, cls.EXPIRED],
            cls.FUNDED: [cls.COOKING, cls.CANCELLED],
            cls.COOKING: [cls.DELIVERING, cls.CANCELLED],
            cls.DELIVERING: [cls.DELIVERED, cls.CANCELLED],
            cls.DELIVERED: [],
            cls.CANCELLED: [],
            cls.EXPIRED: [],
        }
        return transitions.get(current_status, []) 
    
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
    
    @property
    def is_fulfillable(self) -> bool:
        return self not in [self.DELIVERED, self.CANCELLED]


class NotificationChannel(str, Enum):
    """🔔 Canaux de notification supportés"""
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    DASHBOARD = "dashboard"


class UserRole(str, Enum):
    """👥 Rôles utilisateurs avec hiérarchie de permissions"""
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