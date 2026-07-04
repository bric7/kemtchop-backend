# app/entities/production.py
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class Production(Base):
    """
    🍳 Production = Exécution technique en cuisine
    Source de vérité pour les chefs, la température, le conditionnement, etc.
    
    Complémentaire à Campaign (qui gère le côté commercial).
    """
    __tablename__ = "productions"
    
    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("campaigns.id", ondelete="CASCADE"), 
        nullable=False,
        unique=True  # Une production = une campaign (1:1)
    )
    
    # 👨‍🍳 Équipe & Lieu
    chef_name = Column(String(255), nullable=True)
    hub_location = Column(String(100), nullable=True)  # Ex: "Hub Bastos", "Cuisine Centrale"
    
    # 🔥 Données Techniques
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    cooking_temperature = Column(Integer, nullable=True)  # °C
    batch_id = Column(String(64), nullable=True)  # Lot cuisine (ex: "NDL-2026-07-05-01")
    
    # 📦 Conditionnement & Logistique
    packaging_type = Column(String(50), default="Standard")  # Standard, XL, Eco
    dispatch_status = Column(
        String(32), 
        default="pending",
        index=True
    )
    # Valeurs : pending, packed, dispatched, delivered
    
    # 📝 Notes
    notes = Column(Text, nullable=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    campaign = relationship("Campaign", back_populates="production")
    
    def __repr__(self):
        return f"<Production {self.batch_id} - {self.hub_location or 'N/A'}>"