# app/entities/campaign.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base
from app.enums import CampaignStatus


class Campaign(Base):
    __tablename__ = "campaigns"
    
    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    # 📅 Temporel
    target_date = Column(Date, nullable=False, index=True)
    
    # 🎯 Objectif
    minimum_orders = Column(Integer, nullable=False, default=3)
    max_orders = Column(Integer, nullable=True)
    
    # 💰 Pricing
    pack_price = Column(Float, nullable=False)
    early_bird_price = Column(Float, nullable=False)
    standard_price = Column(Float, nullable=False)
    
    # ✅ NOUVEAU : Pourcentage de réduction
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
    orders = relationship("Order", back_populates="campaign", foreign_keys="Order.campaign_id")
    daily_menu = relationship("DailyMenu", foreign_keys=[daily_menu_id])
    pack_launcher_order = relationship("Order", foreign_keys=[pack_launcher_order_id])
    
    # ✅ Contraintes
    __table_args__ = (
        CheckConstraint("minimum_orders > 0", name="chk_min_orders_positive"),
        CheckConstraint("current_orders >= 0", name="chk_current_orders_non_negative"),
        CheckConstraint("pack_price > 0 AND early_bird_price > 0 AND standard_price > 0", name="chk_prices_positive"),
        CheckConstraint("discount_percentage >= 0 AND discount_percentage <= 50", name="chk_discount_range"),
    )
    
    # 🧠 Méthodes métier
    @property
    def status_enum(self) -> CampaignStatus:
        return CampaignStatus(self.status)
    
    @property
    def progress_percentage(self) -> float:
        if self.minimum_orders <= 0:
            return 0.0
        return min(100.0, (self.current_orders / self.minimum_orders) * 100.0)
    
    @property
    def remaining_to_fund(self) -> int:
        return max(0, self.minimum_orders - self.current_orders)
    
    # ✅ NOUVEAU : Montant restant pour atteindre le seuil
    @property
    def remaining_amount(self) -> float:
        """💰 Combien il manque encore pour financer la marmite"""
        target_revenue = self.pack_price  # Prix du pack complet
        return max(0.0, target_revenue - self.current_revenue)
    
    @property
    def is_funded(self) -> bool:
        return self.current_orders >= self.minimum_orders
    
    @property
    def is_active(self) -> bool:
        return self.status_enum in [CampaignStatus.ACTIVE, CampaignStatus.FUNDED]
    
    @property
    def display_price(self) -> float:
        if self.status_enum == CampaignStatus.ACTIVE:
            return self.early_bird_price
        return self.standard_price
    
    def can_transition_to(self, new_status: CampaignStatus) -> bool:
        return new_status in CampaignStatus.get_transitions(self.status_enum)
    
    def __repr__(self):
        return f"<Campaign {self.recipe.name if self.recipe else '?'} - {self.target_date} [{self.current_orders}/{self.minimum_orders}]>"