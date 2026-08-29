from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100))
    product_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
