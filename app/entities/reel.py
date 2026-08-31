from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Reel(Base):
    """
    🎬 Reel = Contenu marketing (vidéo/image) lié à une production (DailyOffer).
    """
    __tablename__ = "reels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)

    # Lien vers l'offre (le cœur de la conversion)
    daily_offer_id = Column(UUID(as_uuid=True), ForeignKey("daily_offers.id", ondelete="SET NULL"), nullable=True)

    # Médias
    video_url = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)

    # Paramètres
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    daily_offer = relationship("DailyOffer", backref="reels")
