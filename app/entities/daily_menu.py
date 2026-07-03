# app/entities/daily_menu.py
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date, Time, 
    ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base
from app.enums import ProductionStatus

# ✅ Pré-calculer les valeurs valides pour la contrainte CHECK (hors de la classe)
_VALID_STATUS_VALUES = "', '".join(s.value for s in ProductionStatus)

class DailyMenu(Base):
    __tablename__ = "daily_menus"
    
    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    # 📅 Temporel
    occurrence_date = Column(Date, nullable=False, index=True)
    cutoff_time = Column(Time, nullable=False, default="18:00:00")
    
    # 🔄 État de production
    status = Column(
        String(32), 
        nullable=False, 
        default=ProductionStatus.PUBLISHED.value,
        index=True
    )
    
    # 📊 Volumes
    minimum_production = Column(Integer, nullable=False, default=3)
    max_production = Column(Integer, nullable=True)
    reserved_portions = Column(Integer, nullable=False, default=0)
    
    # 💰 Pricing
    pack_price = Column(Float, nullable=False)
    individual_price = Column(Float, nullable=False)
    
    # 🔗 Traçabilité
    launch_order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    launched_at = Column(DateTime, nullable=True)
    
    # 🎁 Bonus & notes
    bonus_description = Column(String(255), nullable=True)
    notes = Column(String, nullable=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    product = relationship("Product", back_populates="daily_menus")
    orders = relationship("Order", back_populates="daily_menu")
    launch_order = relationship("Order", foreign_keys=[launch_order_id])
    
    # ✅ Contraintes métier avec contrainte CHECK corrigée
    __table_args__ = (
        UniqueConstraint("product_id", "occurrence_date", name="uq_product_per_day"),
        CheckConstraint("reserved_portions >= 0", name="chk_reserved_non_negative"),
        CheckConstraint("pack_price > 0 AND individual_price > 0", name="chk_prices_positive"),
        CheckConstraint(
            f"status IN ('{_VALID_STATUS_VALUES}')",  # ✅ Syntaxe corrigée
            name="chk_valid_status"
        ),
    )
    
    # 🧠 Méthodes métier type-safe
    @property
    def status_enum(self) -> ProductionStatus:
        return ProductionStatus(self.status)
    
    @property
    def is_accepting_orders(self) -> bool:
        return self.status_enum.is_accepting_orders
    
    @property
    def requires_pack(self) -> bool:
        return self.status_enum == ProductionStatus.PUBLISHED
    
    @property
    def is_in_kitchen(self) -> bool:
        return self.status_enum.is_kitchen_active
    
    @property
    def remaining_capacity(self) -> int | None:
        if self.max_production is None:
            return None
        return max(0, self.max_production - self.reserved_portions)
    
    @property
    def progress_percentage(self) -> float:
        if self.status_enum in [ProductionStatus.CONFIRMED, ProductionStatus.COOKING, ProductionStatus.READY, ProductionStatus.DELIVERED]:
            return 100.0
        if self.minimum_production <= 0:
            return 0.0
        return min(100.0, (self.reserved_portions / self.minimum_production) * 100.0)
    
    def can_transition_to(self, new_status: ProductionStatus) -> bool:
        return new_status in ProductionStatus.get_transitions(self.status_enum)
    
    def __repr__(self):
        return f"<DailyMenu ID {self.id} - {self.occurrence_date} [{self.status}]>"