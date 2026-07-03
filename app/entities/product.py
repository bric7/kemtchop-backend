# app/entities/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Product(Base):
    __tablename__ = "products"
    
    # 🔑 Identité
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 📦 Informations produit
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), default="Tout", index=True)
    image_url = Column(String(500), nullable=True)
    
    # 💰 Pricing de base (catalogue de référence)
    price = Column(Float, nullable=False)
    price_solo = Column(Float, nullable=True)
    price_duo = Column(Float, nullable=True)
    price_family = Column(Float, nullable=True)
    family_size = Column(Integer, default=3)
    
    # 🥗 Accompagnements possibles (Séparés par des virgules)
    complements = Column(String(255), nullable=True)  # Ex: "Bâton de manioc,Manioc vapeur,Plantain frit"
    
    # 🔄 Disponibilité catalogue général
    available = Column(Boolean, default=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    daily_menus = relationship("DailyMenu", back_populates="product", cascade="all, delete-orphan")
    
    # 🧠 Propriété de compatibilité avec tes anciens routeurs
    @property
    def product_name(self) -> str:
        """Alias pour correspondre aux appels 'product.product_name' dans les routes"""
        return self.name

    def __repr__(self):
        return f"<Product {self.name} (ID: {self.id})>"