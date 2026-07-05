# app/entities/collective_pot.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base
from app.enums import CollectivePotStatus


class CollectivePot(Base):
    """
    🍲 CollectivePot = Marmite collective en financement.
    
    Cycle de vie : suggestion → active → funded → cooking → delivering → delivered
    """
    __tablename__ = "collective_pots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    suggestion_id = Column(UUID(as_uuid=True), ForeignKey("suggestions.id"), nullable=True)
    
    # 📅 Temporel
    target_date = Column(Date, nullable=False, index=True)
    
    # 🎯 Objectif Kickstarter
    minimum_orders = Column(Integer, nullable=False, default=3)
    max_orders = Column(Integer, nullable=True)
    
    # 💰 Pricing Business
    preorder_price = Column(Float, nullable=False)
    live_price = Column(Float, nullable=False)
    sponsor_pack_price = Column(Float, nullable=False)
    discount_percentage = Column(Float, nullable=False, default=20.0)
    
    # 📊 Progression
    current_orders = Column(Integer, nullable=False, default=0)
    current_revenue = Column(Float, nullable=False, default=0.0)
    
    # 🔄 État
    status = Column(
        String(32),
        nullable=False,
        default=CollectivePotStatus.ACTIVE.value,
        index=True
    )
    
    # 🎁 Bonus & notes
    bonus_description = Column(String(255), nullable=True)
    admin_notes = Column(String, nullable=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    funded_at = Column(DateTime, nullable=True)
    
    # 🔗 Relations
    product = relationship("Product", back_populates="collective_pots")
    suggestion = relationship(
        "Suggestion",
        back_populates="collective_pot",
        uselist=False,
        foreign_keys=[suggestion_id]  # ← C'est CETTE colonne qui lie CollectivePot → Suggestion
    )
    orders = relationship("Order", back_populates="collective_pot", foreign_keys="Order.collective_pot_id")
    production = relationship("Production", back_populates="collective_pot", uselist=False, cascade="all, delete-orphan")

    # ✅ Contraintes
    __table_args__ = (
        CheckConstraint("minimum_orders > 0", name="chk_cp_min_orders_positive"),
        CheckConstraint("current_orders >= 0", name="chk_cp_current_orders_non_negative"),
        CheckConstraint(
            "preorder_price > 0 AND live_price > 0 AND sponsor_pack_price > 0",
            name="chk_cp_prices_positive"
        ),
        CheckConstraint(
            "discount_percentage >= 0 AND discount_percentage <= 50",
            name="chk_cp_discount_range"
        ),
    )
    
    # 🧠 Propriétés métier
    @property
    def status_enum(self) -> CollectivePotStatus:
        return CollectivePotStatus(self.status)
    
    @property
    def progress_percentage(self) -> float:
        if self.minimum_orders <= 0:
            return 0.0
        return min(100.0, (self.current_orders / self.minimum_orders) * 100.0)
    
    @property
    def remaining_to_fund(self) -> int:
        return max(0, self.minimum_orders - self.current_orders)
    
    @property
    def remaining_capacity(self) -> int:
        if self.max_orders is None:
            return 999
        return max(0, self.max_orders - self.current_orders)
    
    @property
    def remaining_amount(self) -> float:
        return max(0.0, self.sponsor_pack_price - self.current_revenue)
    
    @property
    def is_funded(self) -> bool:
        return self.current_orders >= self.minimum_orders
    
    @property
    def is_active(self) -> bool:
        return self.status_enum in [CollectivePotStatus.ACTIVE, CollectivePotStatus.FUNDED]
    
    @property
    def display_price(self) -> float:
        if self.status_enum == CollectivePotStatus.FUNDED:
            return self.live_price
        return self.preorder_price
    
    def can_transition_to(self, new_status: CollectivePotStatus) -> bool:
        return new_status in CollectivePotStatus.get_transitions(self.status_enum)
    
    def __repr__(self):
        product_name = self.product.name if self.product else '?'
        return f"<CollectivePot {product_name} - {self.target_date} [{self.current_orders}/{self.minimum_orders}]>"