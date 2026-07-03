# app/models/order.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    daily_menu_id = Column(Integer, ForeignKey("daily_menus.id"), nullable=False)
    production_id = Column(Integer, ForeignKey("productions.id"), nullable=False)
    
    portions = Column(Integer, default=1, nullable=False)
    total_amount = Column(Float, nullable=False)
    
    status = Column(String, default="completed") # completed, pending_payment, failed
    delivery_zone = Column(String, nullable=False) # ex: "Bastos", "Mvog-Ada"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Liens
    daily_menu = relationship("DailyMenu")
    production = relationship("Production")