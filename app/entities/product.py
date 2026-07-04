# app/entities/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Product(Base):
    """
    📦 Product = Recette du catalogue permanent
    Version simplifiée pour correspondre exactement à la BDD
    """
    __tablename__ = "products"
    
    # 🔑 Identité
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 📦 Informations produit (COLONNES EXISTANTES EN BDD)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), default="Tout", index=True)
    image_url = Column(String(500), nullable=True)
    
    # 💰 Pricing de base (UNE SEULE COLONNE price)
    price = Column(Float, nullable=False)
    
    # 🔄 Disponibilité
    available = Column(Boolean, default=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations
    campaigns = relationship(
        "Campaign", 
        back_populates="recipe", 
        cascade="all, delete-orphan"
    )
    daily_menus = relationship(
        "DailyMenu", 
        back_populates="product", 
        cascade="all, delete-orphan"
    )
    
    # 🧠 Propriété de compatibilité
    @property
    def product_name(self) -> str:
        return self.name
    
    def __repr__(self):
        return f"<Product {self.name} (ID: {self.id})>"