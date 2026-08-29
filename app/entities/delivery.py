from sqlalchemy import Column, Integer, JSON
from app.database import Base

class DeliverySettings(Base):
    __tablename__ = "delivery_settings"
    id = Column(Integer, primary_key=True, index=True)
    zones = Column(JSON)
    base_price = Column(Integer, default=1000)
