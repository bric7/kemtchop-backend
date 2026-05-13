from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.ext.declarative import declarative_base
from app.database import SessionLocal, engine
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    # ICI : Il faut absolument primary_key=True
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
    # Tes nouveaux champs pour l'affiliation
    is_affiliate = Column(Boolean, default=False)
    affiliate_code = Column(String, unique=True, index=True, nullable=True)
    pending_commissions = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0) 
    last_payout_date = Column(DateTime, nullable=True)
    expo_push_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    has_requested_affiliate = Column(Boolean, default=False)

class PaymentStatus(enum.Enum):
    PENDING = "en_attente"
    PARTIAL = "acompte_paye"
    COMPLETED = "termine"
    CANCELLED = "annule"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    # On utilise du texte simple pour éviter les erreurs de Foreign Key au début
    product_name = Column(String, nullable=False) 
    customer_name = Column(String, nullable=False)
    phone = Column(String, nullable=False, index=True)
    zone = Column(String, nullable=False) # Quartier (Akwa, Bastos, etc.)
    delivery_date = Column(String)  # Ex: "2026-04-15"
    delivery_time = Column(String)
    affiliate_payout_phone = Column(String, nullable=True)
    commission_paid = Column(Boolean, default=False)
    affiliate_code = Column(String, nullable=True, index=True)
    
    
    # On garde des noms uniques et clairs
    total_amount = Column(Float, nullable=False) 
    deposit_amount = Column(Float, nullable=False) 
    
    portion_size = Column(String)
    complement = Column(String) # Accompagnement (Frites, Riz, etc.)
    option_selected = Column(String)
    
    
    # Statut (Assure-toi que PaymentStatus est bien importé)
    status = Column(String, default="en_attente", index=True) # Plus simple que Enum pour le debug
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    transactions = relationship("Transaction", back_populates="order")

    # Si tu as une table Transaction, garde la relation, sinon commente-la
    # transactions = relationship("Transaction", back_populates="order")

class PaymentMethod(enum.Enum):
    ORANGE_MONEY = "orange_money"
    MTN_MOBILE_MONEY = "mtn_mobile_money"
    CASH = "cash"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    amount = Column(Integer, nullable=False)
    
    # Type: 'deposit' (acompte) ou 'balance' (solde)
    transaction_type = Column(String, nullable=False) 
    
    # Reference de l'opérateur (Orange Money / MTN / etc.)
    payment_reference = Column(String, unique=True)
    status = Column(String, default="success")
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="transactions")
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    operator_reference = Column(String, unique=True)


# Ajoute ceci à la suite de tes autres modèles dans app/models.py

class Reel(Base):
    __tablename__ = "reels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String) # Ex: "Le meilleur Eru de Bastos"
    product_name = Column(String) # Le nom du plat lié
    price = Column(Float) # Le prix total du plat
    price_solo = Column(Float)  # Ajoute ceci
    price_duo = Column(Float)
    category = Column(String, default="Grillades")
    is_available = Column(Boolean, default=True)
    price_family = Column(Float)
    family_size = Column(Integer, default=3)
    complements = Column(String)
    likes_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String) # Obligatoire
    video_url = Column(String, nullable=True) # Optionnel

class DeliverySettings(Base):
    __tablename__ = "delivery_settings"
    id = Column(Integer, primary_key=True, index=True)
    zones = Column(JSON)  # PostgreSQL gère très bien le format JSON
    base_price = Column(Integer, default=1000)

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False) # ou total_amount pour rester cohérent
    image_url = Column(String)
    category = Column(String) # ex: "Entrée", "Résistance"
    is_hero = Column(Boolean, default=False)

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True)
    event_type = Column(String) # "click_reel", "order_start", "view_video"
    product_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)  # Token cryptographique
    phone = Column(String, nullable=False)  # Lié à l'utilisateur
    expires_at = Column(DateTime, nullable=False)  # Expiration
    used = Column(Boolean, default=False)  # Évite la réutilisation
    created_at = Column(DateTime, default=datetime.utcnow)

