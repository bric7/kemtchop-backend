# app/enums.py
"""
🎯 Enums centralisés pour KemTchop
Évite les fautes de frappe, permet l'autocomplétion, et documente les états valides.
"""

from enum import Enum, auto
from typing import List


class ProductionStatus(str, Enum):
    """📊 Cycle de vie d'une production (DailyMenu)"""
    
    DRAFT = "draft"              # Brouillon admin (non visible)
    PUBLISHED = "published"      # Visible, votes/réservations ouverts
    CONFIRMED = "confirmed"      # Seuil atteint, cuisine démarrée
    COOKING = "cooking"          # En préparation active
    READY = "ready"              # Prêt pour livraison
    DELIVERED = "delivered"      # Livré, archivé
    CANCELLED = "cancelled"      # Annulé (avec raison loggée)
    
    @property
    def is_accepting_orders(self) -> bool:
        """Le menu accepte-t-il de nouvelles réservations ?"""
        return self in [self.PUBLISHED, self.CONFIRMED]
    
    @property
    def is_terminal(self) -> bool:
        """État final : pas de transition possible"""
        return self in [self.DELIVERED, self.CANCELLED]
    
    @property
    def is_kitchen_active(self) -> bool:
        """La cuisine est-elle en train de travailler sur ce menu ?"""
        return self in [self.CONFIRMED, self.COOKING, self.READY]
    
    @classmethod
    def get_transitions(cls, current: "ProductionStatus") -> List["ProductionStatus"]:
        """Retourne les statuts vers lesquels on peut transitionner"""
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


class OrderStatus(str, Enum):
    """📦 Cycle de vie d'une commande client"""
    
    PENDING = "pending"          # En attente de paiement acompte
    PAID = "paid"                # Acompte payé, en attente production
    CONFIRMED = "confirmed"      # Production confirmée
    PREPARING = "preparing"      # En cuisine
    READY = "ready"              # Prêt à livrer
    OUT_FOR_DELIVERY = "out_for_delivery"  # En route
    DELIVERED = "delivered"      # Livré au client
    CANCELLED = "cancelled"      # Annulé (client ou admin)
    
    @property
    def is_paid(self) -> bool:
        """L'acompte a-t-il été payé ?"""
        return self in [self.PAID, self.CONFIRMED, self.PREPARING, self.READY, self.OUT_FOR_DELIVERY, self.DELIVERED]
    
    @property
    def is_fulfillable(self) -> bool:
        """La commande peut-elle encore être préparée/livrée ?"""
        return self not in [self.DELIVERED, self.CANCELLED]


class NotificationChannel(str, Enum):
    """🔔 Canaux de notification supportés"""
    
    PUSH = "push"                # Expo Push Notifications
    SMS = "sms"                  # Twilio / Africa's Talking
    EMAIL = "email"              # SendGrid / Resend
    WHATSAPP = "whatsapp"        # WhatsApp Business API
    DASHBOARD = "dashboard"      # Mise à jour WebSocket/SSE


class UserRole(str, Enum):
    """👥 Rôles utilisateurs avec hiérarchie de permissions"""
    
    CUSTOMER = "customer"        # Client standard
    AFFILIATE = "affiliate"      # Client + code parrainage
    LIVREUR = "livreur"          # Livreur (accès commandes assignées)
    CUISINE = "cuisine"          # Chef / équipe cuisine
    MANAGER = "manager"          # Gestionnaire hub (stats, équipes)
    ADMIN = "admin"              # Admin plateforme (tous hubs)
    SUPER_ADMIN = "super_admin"  # Super admin (settings globaux)
    
    @property
    def hierarchy_level(self) -> int:
        """Niveau hiérarchique pour comparaison de permissions"""
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
        """Un utilisateur peut-il accéder à une ressource de ce rôle ?"""
        return self.hierarchy_level >= resource_role.hierarchy_level