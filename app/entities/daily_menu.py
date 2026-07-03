# app/models/daily_menu.py
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Date, Time, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.database import Base 
from app.entities.product import Product 
Base = declarative_base()

class DailyMenu(Base):
    __tablename__ = "daily_menus"
    
    # Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    # 📅 Temporel
    occurrence_date = Column(Date, nullable=False, index=True)  # "2024-06-15"
    cutoff_time = Column(Time, nullable=False, default="22:00:00")  # Heure limite
    
    # 🔄 État de production (source de vérité)
    status = Column(String(32), nullable=False, default="SCHEDULED", index=True)
    # Valeurs valides : SCHEDULED, PREORDER_OPEN, PRODUCTION_CONFIRMED, PRODUCTION_CLOSED, DELIVERED
    
    # 📊 Volumes
    minimum_production = Column(Integer, nullable=False, default=3)
    max_production = Column(Integer, nullable=True)  # NULL = illimité
    reserved_portions = Column(Integer, nullable=False, default=0)
    
    # 💰 Pricing spécifique à l'occurrence
    pack_price = Column(Float, nullable=False)  # Prix du pack de lancement
    individual_price = Column(Float, nullable=False)  # Prix portion individuelle
    
    # 🔗 Traçabilité
    launch_order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    launched_at = Column(DateTime, nullable=True)
    
    # 🎁 Bonus & notes
    bonus_description = Column(String(255), nullable=True)  # "Jus offert"
    notes = Column(String, nullable=True)  # Notes internes cuisine
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    product = relationship("Product", back_populates="daily_menus")
    orders = relationship("Order", back_populates="daily_menu")
    launch_order = relationship("Order", foreign_keys=[launch_order_id])
    
    # ✅ Contraintes métier
    __table_args__ = (
        UniqueConstraint("product_id", "occurrence_date", name="uq_product_per_day"),
        CheckConstraint("reserved_portions >= 0", name="chk_reserved_non_negative"),
        CheckConstraint("pack_price > 0 AND individual_price > 0", name="chk_prices_positive"),
        CheckConstraint(
            "status IN ('SCHEDULED', 'PREORDER_OPEN', 'PRODUCTION_CONFIRMED', 'PRODUCTION_CLOSED', 'DELIVERED')",
            name="chk_valid_status"
        ),
    )
    
    # 🧠 Méthodes métier (source de vérité des statuts)
    @property
    def is_accepting_orders(self) -> bool:
        """Le menu accepte-t-il de nouvelles commandes ?"""
        return self.status in ["PREORDER_OPEN", "PRODUCTION_CONFIRMED"]
    
    @property
    def requires_pack(self) -> bool:
        """Faut-il un pack pour lancer la production ?"""
        return self.status == "PREORDER_OPEN"
    
    @property
    def remaining_capacity(self) -> int | None:
        """Places restantes (None si illimité)"""
        if self.max_production is None:
            return None
        return max(0, self.max_production - self.reserved_portions)
    
    @property
    def progress_percentage(self) -> float:
        """Progression vers le seuil de lancement (%)"""
        if self.status == "PRODUCTION_CONFIRMED":
            return 100.0
        if self.minimum_production <= 0:
            return 0.0
        return min(100, (self.reserved_portions / self.minimum_production) * 100)
    
    def can_transition_to(self, new_status: str) -> bool:
        """Valide les transitions d'état autorisées"""
        transitions = {
            "SCHEDULED": ["PREORDER_OPEN"],
            "PREORDER_OPEN": ["PRODUCTION_CONFIRMED", "PRODUCTION_CLOSED"],
            "PRODUCTION_CONFIRMED": ["PRODUCTION_CLOSED", "DELIVERED"],
            "PRODUCTION_CLOSED": ["DELIVERED"],
            "DELIVERED": [],  # Terminal
        }
        return new_status in transitions.get(self.status, [])
    
    def __repr__(self):
        return f"<DailyMenu {self.product.name} - {self.occurrence_date} [{self.status}]>"