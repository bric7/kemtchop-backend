# app/entities/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Product(Base):
    """
    📦 Product = Recette du catalogue permanent
    Version STRICTEMENT conforme au schéma BDD existant
    """
    __tablename__ = "products"
    
    # 🔑 Identité
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 📦 Informations produit (COLONNES EXISTANTES EN BDD)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(255), nullable=True)  # VARCHAR pas TEXT
    category = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    
    # 💰 Pricing (COLONNES EXISTANTES EN BDD)
    price = Column(Float, nullable=False)
    price_solo = Column(Float, nullable=True)
    price_duo = Column(Float, nullable=True)
    price_family = Column(Float, nullable=True)
    family_size = Column(Integer, nullable=True)
    
    # 🥗 Accompagnements
    complements = Column(String(255), nullable=True)
    
    # 🎯 Hero flag
    is_hero = Column(Boolean, nullable=True)
    
    # ❌ PAS DE COLONNES : available, created_at, updated_at (n'existent pas en BDD)
    
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