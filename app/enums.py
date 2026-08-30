# app/enums.py
"""
🎯 Architecture Métier KemTchop v2.1 - La Séparation Production/Service
"""

from enum import Enum
from typing import List


class ProductionStatus(str, Enum):
    """📊 Cycle de vie d'une production culinaire (La Marmite)"""
    
    PROPOSED = "proposed"       # Offre en ligne, en attente du seuil (J+1 ou plus)
    CONFIRMED = "confirmed"     # Production garantie (Seuil atteint ou forcée)
    COOKING = "cooking"         # 🔥 En cours de préparation en cuisine
    READY = "ready"             # ✅ Plats prêts à être servis/expédiés
    COMPLETED = "completed"     # 🏁 Fin de service / Épuisé
    CANCELLED = "cancelled"     # ❌ Annulation exceptionnelle

    @property
    def is_accepting_orders(self) -> bool:
        """
        Loi de Vente : On peut commander tant que la production n'est pas terminée
        et qu'il reste de la capacité (vérifié dans la route).
        """
        return self in [self.PROPOSED, self.CONFIRMED, self.COOKING, self.READY]


class OrderStatus(str, Enum):
    """📦 Cycle de vie d'une commande individuelle (Le Client)"""
    
    PENDING = "pending"             # Clic fait, en attente de paiement
    PAID = "paid"                   # ✅ Acompte/Paiement reçu. Engagement client validé.
    PREPARING = "preparing"         # La marmite liée est en mode COOKING
    READY_TO_SHIP = "ready_to_ship" # Le plat individuel est emballé
    SHIPPING = "shipping"           # 🚚 Le livreur a pris cette commande précise
    DELIVERED = "delivered"         # 😋 Remis au client
    CANCELLED = "cancelled"         # Annulation (remboursée ou non selon politique)
    
    @property
    def is_active(self) -> bool:
        return self not in [self.CANCELLED, self.DELIVERED]
