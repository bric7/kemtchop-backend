# app/entities/production.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class Production(Base):
    """
    🍳 Production = Exécution technique en cuisine.
    
    Source de vérité pour les chefs : température, conditionnement, hub.
    Liée 1:1 à un CollectivePot (la marmite commerciale).
    
    Architecture : CollectivePot (commercial) → Production (technique)
    """
    __tablename__ = "productions"
    
    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collective_pot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collective_pots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # 1 Production = 1 CollectivePot
    )
    
    # 👨‍🍳 Équipe & Lieu
    chef_name = Column(String(255), nullable=True)
    hub_location = Column(String(100), nullable=True)
    
    # 🔥 Données Techniques
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    cooking_temperature = Column(Integer, nullable=True)
    batch_id = Column(String(64), nullable=True)
    
    # 📦 Conditionnement & Logistique
    packaging_type = Column(String(50), default="Standard")
    dispatch_status = Column(String(32), default="pending", index=True)
    # Valeurs : pending, packed, dispatched, delivered
    
    # 📝 Notes
    notes = Column(Text, nullable=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    collective_pot = relationship("CollectivePot", back_populates="production")
    
    def __repr__(self):
        return f"<Production {self.batch_id} - {self.hub_location or 'N/A'}>"