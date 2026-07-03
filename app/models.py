# app/models.py - IMPORTS CORRIGÉS (début du fichier)

from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Float, 
    Boolean, 
    DateTime, 
    Numeric,      # ✅ Pour cart_value dans UserEvent
    func,
    ForeignKey,
    Enum          # ✅ AJOUT CRITIQUE : Enum de SQLAlchemy (pas le module enum Python !)
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSON  # ✅ Pour PostgreSQL JSONB
# ✅ Module enum Python pour définir tes enums (PaymentStatus, PaymentMethod)
import enum
from datetime import datetime

# ✅ Base déclarative (une seule fois)
Base = declarative_base()

# ============================================================
# TES MODÈLES (inchangés, juste pour référence)
# ============================================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True) 
    username = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True)
    customer_name = Column(String)
    hashed_password = Column(String)
    permissions = Column(String, default="dashboard")
    role = Column(String)
    is_active = Column(Boolean, default=True)
    can_view_stats = Column(Boolean, default=False)
    can_edit_orders = Column(Boolean, default=False)
    is_affiliate = Column(Boolean, default=False)
    affiliate_code = Column(String, unique=True, index=True, nullable=True)
    pending_commissions = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0) 
    last_payout_date = Column(DateTime, nullable=True)
    expo_push_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    has_requested_affiliate = Column(Boolean, default=False)

# ✅ Enums Python (pour définir les valeurs possibles)
class PaymentStatus(enum.Enum):
    PENDING = "en_attente"
    PARTIAL = "acompte_paye"
    COMPLETED = "termine"
    CANCELLED = "annule"

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, nullable=False) 
    customer_name = Column(String, nullable=False)
    phone = Column(String, nullable=False, index=True)
    zone = Column(String, nullable=False)
    delivery_date = Column(String)
    delivery_time = Column(String)
    affiliate_payout_phone = Column(String, nullable=True)
    commission_paid = Column(Boolean, default=False)
    affiliate_code = Column(String, nullable=True, index=True)
    total_amount = Column(Float, nullable=False) 
    deposit_amount = Column(Float, nullable=False) 
    portion_size = Column(String)
    complement = Column(String)
    option_selected = Column(String)
    status = Column(String, default="en_attente", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    transactions = relationship("Transaction", back_populates="order")
    idempotency_key = Column(String, unique=True, nullable=True, index=True)

# ✅ Autre enum Python
class PaymentMethod(enum.Enum):
    ORANGE_MONEY = "orange_money"
    MTN_MOBILE_MONEY = "mtn_mobile_money"
    CASH = "cash"

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    payment_reference = Column(String, unique=True)
    status = Column(String, default="success")
    created_at = Column(DateTime, default=datetime.utcnow)
    order = relationship("Order", back_populates="transactions")
    
    # ✅ Enum de SQLAlchemy pour le champ payment_method
    payment_method = Column(Enum(PaymentMethod), nullable=True)  # ✅ Enum importé de sqlalchemy
    operator_reference = Column(String, unique=True)

class Reel(Base):
    __tablename__ = "reels"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    product_name = Column(String)
    price = Column(Float)
    price_solo = Column(Float)
    price_duo = Column(Float)
    category = Column(String, default="Grillades")
    is_available = Column(Boolean, default=True)
    price_family = Column(Float)
    family_size = Column(Integer, default=3)
    complements = Column(String)
    likes_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String)
    video_url = Column(String, nullable=True)

class DeliverySettings(Base):
    __tablename__ = "delivery_settings"
    id = Column(Integer, primary_key=True, index=True)
    zones = Column(JSON)
    base_price = Column(Integer, default=1000)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    image_url = Column(String)
    category = Column(String)
    is_hero = Column(Boolean, default=False)

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True)
    event_type = Column(String)
    product_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserEvent(Base):
    __tablename__ = "user_events"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    product_id = Column(Integer, nullable=True)
    product_name = Column(String(255), nullable=True)
    video_id = Column(Integer, nullable=True)
    cart_value = Column(Numeric(10, 2), nullable=True)
    affiliate_code = Column(String(20), nullable=True)
    
    # ✅ RENOMMÉ : metadata → event_metadata (car 'metadata' est réservé)
    event_metadata = Column(JSON, default=dict, nullable=True)  
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    session_id = Column(String(100), nullable=True)
    
    # Relation optionnelle vers User
    user = relationship("User", foreign_keys=[phone], primaryjoin="UserEvent.phone == User.phone")
