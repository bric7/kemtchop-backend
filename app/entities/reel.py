from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from app.database import Base

class Reel(Base):
    __tablename__ = "reels"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    product_name = Column(String(255))
    price = Column(Float)
    price_solo = Column(Float)
    price_duo = Column(Float)
    category = Column(String(100), default="Grillades")
    is_available = Column(Boolean, default=True)
    price_family = Column(Float)
    family_size = Column(Integer, default=3)
    complements = Column(String(255))
    likes_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String(500))
    video_url = Column(String(500), nullable=True)
