# app/entities/production.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.database import Base

class Production(Base):
    __tablename__ = "productions"
    
    # 🔑 Identifiant unique de la marmite / du lot physique
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 🔗 Liens logistiques
    daily_menu_id = Column(UUID(as_uuid=True), ForeignKey("daily_menus.id", ondelete="CASCADE"), nullable=False)
    
    # 🏢 Localisation (Anticipation de tes hubs physiques au Cameroun)
    hub_location = Column(String(100), default="Yaoundé - Bastos") # Douala, Bertoua, Garoua
    
    # 🧑‍🍳 Facteurs Humains & Temps
    chef_name = Column(String(100), nullable=True)
    status = Column(String(32), default="planifie") # planifie, en_preparation, cooking, completed, annule
    
    estimated_start_time = Column(DateTime, nullable=True)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    
    # 📊 Gestion des jauges industrielles
    max_capacity = Column(Integer, default=90)
    reserved_portions = Column(Integer, default=0)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations ORM
    daily_menu = relationship("DailyMenu", back_populates="productions")
    orders = relationship("Order", back_populates="production")