# app/models/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base  # ← Base doit être exportée (vérifié ✅ plus haut)

class Product(Base):
    __tablename__ = "products"
    
    # 🔑 Identité
    id = Column(Integer, primary_key=True, autoincrement=True)  # ← INTEGER, cohérent avec daily_menus
    
    # 📦 Informations produit
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), default="Tout", index=True)
    image_url = Column(String(500), nullable=True)
    
    # 💰 Pricing de base (catalogue)
    price = Column(Float, nullable=False)  # Prix de référence
    price_solo = Column(Float, nullable=True)
    price_duo = Column(Float, nullable=True)
    price_family = Column(Float, nullable=True)
    family_size = Column(Integer, default=3)
    
    # 🥗 Accompagnements
    complements = Column(String(255), nullable=True)  # Ex: "Bâton,Manioc,Plantain"
    
    # 🔄 Disponibilité
    available = Column(Boolean, default=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    daily_menus = relationship("DailyMenu", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Product {self.name} (ID: {self.id})>"