import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class PaymentStatus(enum.Enum):
    PENDING = "en_attente"
    PARTIAL = "acompte_paye"
    COMPLETED = "termine"
    CANCELLED = "annule"

class PaymentMethod(enum.Enum):
    ORANGE_MONEY = "orange_money"
    MTN_MOBILE_MONEY = "mtn_mobile_money"
    CASH = "cash"

class Order(Base):
    """
    🛒 Order = Engagement client individuel sur une marmite collective ou commande directe.
    """
    __tablename__ = "orders"

    # 🔑 Identité (Transition vers UUID mais support des champs existants)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Lien vers l'offre quotidienne (DailyOffer)
    daily_offer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("daily_offers.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # 👤 Client
    user_id = Column(String(255), nullable=True, index=True)
    customer_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False, index=True)

    # 📦 Détails Commande
    product_name = Column(String(255), nullable=True)
    portions = Column(Integer, nullable=False, default=1)
    portion_size = Column(String(100), nullable=True)
    complement = Column(String(255), nullable=True)
    option_selected = Column(String(255), nullable=True)

    # 🚚 Livraison
    zone = Column(String(100), nullable=True)
    delivery_date = Column(String(100), nullable=True)
    delivery_time = Column(String(100), nullable=True)

    # 💰 Finances
    total_amount = Column(Float, nullable=False)
    deposit_amount = Column(Float, nullable=False, default=0.0)
    is_sponsor = Column(Boolean, default=False)

    # 💳 Statut & Paiement
    status = Column(String(32), default="en_attente", index=True) # Compatibilité anciens modèles
    payment_status = Column(String(32), default="pending", index=True)
    payment_method_name = Column(String(50), nullable=True) # pour pas de conflit avec l'enum
    transaction_id = Column(String(255), nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=True, index=True)

    # 🎟️ Affiliation
    affiliate_code = Column(String(50), nullable=True, index=True)
    affiliate_payout_phone = Column(String(20), nullable=True)
    commission_paid = Column(Boolean, default=False)

    # 📝 Notes & Audit
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 🔗 Relations
    daily_offer = relationship("DailyOffer", back_populates="orders")
    transactions = relationship("Transaction", back_populates="order")

    def __repr__(self):
        return f"<Order {self.id} - customer={self.customer_name} - {self.total_amount} XAF>"

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)
    payment_reference = Column(String(255), unique=True)
    status = Column(String(32), default="success")
    created_at = Column(DateTime, default=datetime.utcnow)

    payment_method = Column(Enum(PaymentMethod), nullable=True)
    operator_reference = Column(String(255), unique=True)

    order = relationship("Order", back_populates="transactions")
