# app/entities/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Product(Base):
    """
    📦 Product = Recette du catalogue permanent
    Exemple : "Ndolé Royal", "Poulet DG", "Koki"
    
    Un Product existe indépendamment du temps.
    Il peut être proposé plusieurs jours différents via Campaign.
    """
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
    
    # 🥗 Accompagnements possibles (séparés par virgules)
    complements = Column(String(255), nullable=True)
    
    # 🔄 Disponibilité catalogue général
    available = Column(Boolean, default=True)
    
    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🔗 Relations (Product est le PARENT, Campaign et DailyMenu pointent vers lui)
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
        """Alias pour compatibilité avec les anciens appels"""
        return self.name
    
    def __repr__(self):
        return f"<Product {self.name} (ID: {self.id})>"