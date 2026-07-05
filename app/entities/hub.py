# app/entities/hub.py
from sqlalchemy import Column, String, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base

class Hub(Base):
    __tablename__ = "hubs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=True)
    active_productions = Column(Integer, default=0)
    pending_orders = Column(Integer, default=0)
    revenue_today = Column(Float, default=0.0)