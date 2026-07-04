# app/entities/campaign.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base
from app.enums import CampaignStatus


class Campaign(Base):
    """
    🎯 Campaign = Session de précommande collective (modèle Kickstarter)
    
    Exemple : "Ndolé demain, objectif 3 portions"
    - preorder_price (1500F) : prix AVANT que la marmite soit lancée
    - live_price (1200F) : prix APRÈS le lancement (réduction collective)
    - sponsor_pack_price (4500F) : prix pour financer TOUTE la marmite
    """
    __tablename__ = "campaigns"
    
    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    # 📅 Temporel
    target_date = Column(Date, nullable=False, index=True)
    
    # 🎯 Objectif Kickstarter
    minimum_orders = Column(Integer, nullable=False, default=3)
    max_orders = Column(Integer, nullable=True)  # NULL = illimité
    
    # 💰 Pricing Business (NOMS CLAIRS)
    preorder_price = Column(Float, nullable=False)        # Prix avant seuil (ex: 1500F)
    live_price = Column(Float, nullable=False)            # Prix après seuil (ex: 1200F)
    sponsor_pack_price = Column(Float, nullable=False)    # Prix pour financer tout (ex: 4500F)
    
    # 📊 Réduction appliquée après lancement (%)
    discount_percentage = Column(Float, nullable=False, default=20.0)
    
    # 📊 Progression
    current_orders = Column(Integer, nullable=False, default=0)
    current_revenue = Column(Float, nullable=False, default=0.0)
    
    # 🔄 État
    status = Column(
        String(32),
        nullable=False,
        default=CampaignStatus.ACTIVE.value,
        index=True
    )
    
    # 🔗 Liens
    daily_menu_id = Column(UUID(as_uuid=True), ForeignKey("daily_menus.id"), nullable=True)
    pack_launcher_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # 🎁 Bonus & notes
    bonus_description = Column(String(255), nullable=True)
    admin_notes = Column(String, nullable=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    funded_at = Column(DateTime, nullable=True)
    
    # 🔗 Relations
    recipe = relationship("Product", back_populates="campaigns")
    orders = relationship(
        "Order", 
        back_populates="campaign", 
        foreign_keys="Order.campaign_id"
    )
    daily_menu = relationship("DailyMenu", foreign_keys=[daily_menu_id])
    pack_launcher_order = relationship("Order", foreign_keys=[pack_launcher_order_id])
    production = relationship(
        "Production", 
        back_populates="campaign", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    
    # ✅ Contraintes métier (noms mis à jour)
    __table_args__ = (
        CheckConstraint("minimum_orders > 0", name="chk_min_orders_positive"),
        CheckConstraint("current_orders >= 0", name="chk_current_orders_non_negative"),
        CheckConstraint(
            "preorder_price > 0 AND live_price > 0 AND sponsor_pack_price > 0",
            name="chk_prices_positive"
        ),
        CheckConstraint(
            "discount_percentage >= 0 AND discount_percentage <= 50",
            name="chk_discount_range"
        ),
    )
    
    # ============================================================
    # 🧠 MÉTHODES MÉTIER
    # ============================================================
    
    @property
    def status_enum(self) -> CampaignStatus:
        """Retourne le statut comme Enum"""
        return CampaignStatus(self.status)
    
    @property
    def progress_percentage(self) -> float:
        """Progression vers l'objectif Kickstarter (0-100%)"""
        if self.minimum_orders <= 0:
            return 0.0
        return min(100.0, (self.current_orders / self.minimum_orders) * 100.0)
    
    @property
    def remaining_to_fund(self) -> int:
        """Nombre de portions restantes avant lancement"""
        return max(0, self.minimum_orders - self.current_orders)
    
    @property
    def remaining_capacity(self) -> int:
        """Places restantes avant saturation (999 si illimité)"""
        if self.max_orders is None:
            return 999
        return max(0, self.max_orders - self.current_orders)
    
    @property
    def remaining_amount(self) -> float:
        """💰 Montant restant pour financer la marmite"""
        return max(0.0, self.sponsor_pack_price - self.current_revenue)
    
    @property
    def is_funded(self) -> bool:
        """Le seuil Kickstarter est-il atteint ?"""
        return self.current_orders >= self.minimum_orders
    
    @property
    def is_active(self) -> bool:
        """La campaign accepte-t-elle encore des commandes ?"""
        return self.status_enum in [CampaignStatus.ACTIVE, CampaignStatus.FUNDED]
    
    @property
    def display_price(self) -> float:
        """
        Prix affiché au client (dépend de l'état de financement)
        - Avant lancement : preorder_price (1500F)
        - Après lancement : live_price (1200F)
        """
        if self.status_enum == CampaignStatus.FUNDED:
            return self.live_price
        return self.preorder_price
    
    def can_transition_to(self, new_status: CampaignStatus) -> bool:
        """Valide les transitions d'état autorisées"""
        return new_status in CampaignStatus.get_transitions(self.status_enum)
    
    def __repr__(self):
        recipe_name = self.recipe.name if self.recipe else '?'
        return (
            f"<Campaign {recipe_name} - {self.target_date} "
            f"[{self.current_orders}/{self.minimum_orders}]>"
        )