# app/entities/order.py
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class Order(Base):
    """
    🛒 Order = Engagement client individuel sur une marmite collective.

    Architecture : CollectivePot → Order (1:N)
    """
    __tablename__ = "orders"

    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ✅ RENOMMÉ : campaign_id → collective_pot_id
    collective_pot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collective_pots.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 👤 Client
    user_id = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    user_phone = Column(String(20), nullable=True)

    # 📦 Commande
    portions = Column(Integer, nullable=False, default=1)
    is_sponsor = Column(Boolean, default=False)
    total_amount = Column(Float, nullable=False)
    deposit_amount = Column(Float, nullable=False)

    # 💳 Paiement
    payment_status = Column(String(32), default="pending", index=True)
    # Valeurs : pending, paid, refunded, cancelled
    payment_method = Column(String(50), nullable=True)
    transaction_id = Column(String(255), nullable=True)

    # 🎟️ Affiliate
    affiliate_code = Column(String(50), nullable=True)

    # 📝 Notes
    notes = Column(Text, nullable=True)

    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 🔗 Relations
    # ✅ RENOMMÉ : campaign → collective_pot
    collective_pot = relationship("CollectivePot", back_populates="orders")

    def __repr__(self):
        return f"<Order {self.id} - user={self.user_id} - {self.portions} portions>"