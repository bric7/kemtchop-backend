# app/entities/order.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base
from app.enums import OrderStatus


class Order(Base):
    __tablename__ = "orders"
    
    # 🔑 Identité
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # 🔗 Clés Étrangères (MODIFIÉ pour supporter Campaign)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    daily_menu_id = Column(UUID(as_uuid=True), ForeignKey("daily_menus.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    
    # 👤 Informations Client
    customer_name = Column(String(255), nullable=False)
    phone = Column(String(32), nullable=False, index=True)
    zone = Column(String(100), nullable=False)
    
    # 💰 Financier
    total_amount = Column(Float, nullable=False)
    deposit_amount = Column(Float, nullable=False, default=0.0)
    
    # 🍲 Spécificités
    mode = Column(String(32), nullable=False)  # "pack" ou "portion"
    portions = Column(Integer, nullable=False, default=1)
    portion_size = Column(String(32), nullable=False, default="Standard")
    complement = Column(String(255), nullable=True)
    
    # 📦 Suivi
    status = Column(
        String(32),
        nullable=False,
        default=OrderStatus.PENDING.value,
        index=True
    )
    delivery_date = Column(String(32), nullable=False)
    delivery_time = Column(String(32), nullable=False)
    
    # 💸 Affiliation
    affiliate_code = Column(String(64), nullable=True, index=True)
    affiliate_payout_phone = Column(String(32), nullable=True)
    commission_paid = Column(DateTime, nullable=True)
    
    # 🛡️ Sécurité
    idempotency_key = Column(String(255), nullable=True, unique=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations (CORRIGÉES)
    campaign = relationship(
        "Campaign",
        back_populates="orders",
        foreign_keys=[campaign_id]
    )
    daily_menu = relationship(
        "DailyMenu",
        foreign_keys=[daily_menu_id]
    )
    product = relationship("Product")
    
    # 🧠 Méthodes
    @property
    def status_enum(self) -> OrderStatus:
        return OrderStatus(self.status)
    
    @property
    def is_paid(self) -> bool:
        return self.status_enum.is_paid
    
    @property
    def is_fulfillable(self) -> bool:
        return self.status_enum.is_fulfillable
    
    def __repr__(self):
        return f"<Order #{self.id} - {self.customer_name} [{self.status}]>"