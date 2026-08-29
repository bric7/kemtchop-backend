import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Numeric, func, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON
from app.database import Base

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
    event_metadata = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    session_id = Column(String(100), nullable=True)

    user = relationship("User", foreign_keys=[phone], primaryjoin="UserEvent.phone == User.phone")
