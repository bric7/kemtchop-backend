import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Reel(Base):
    """
    🎬 Reel = Contenu marketing (vidéo/image).
    Peut être lié à une offre active (v3) ou être un contenu permanent (Legacy).
    """
    __tablename__ = "reels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=True)

    # --- NOUVEAU (v3.0) ---
    daily_offer_id = Column(UUID(as_uuid=True), ForeignKey("daily_offers.id", ondelete="SET NULL"), nullable=True)

    # --- COMPATIBILITÉ (Legacy/Admin) ---
    product_name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    price = Column(Float, nullable=True)
    price_solo = Column(Float, nullable=True)
    price_duo = Column(Float, nullable=True)
    price_family = Column(Float, nullable=True)
    family_size = Column(Integer, default=3)
    complements = Column(String(255), nullable=True)
    is_available = Column(Boolean, default=True) # Utilisé par l'admin

    # Médias
    video_url = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)

    # Paramètres d'affichage
    is_active = Column(Boolean, default=True) # Utilisé par le flux utilisateur
    priority = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    daily_offer = relationship("DailyOffer", backref="reels")
