# app/entities/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Product(Base):
    """
    📦 Product = Recette du catalogue permanent KemTchop.
    
    Architecture définitive :
    Product → Suggestion → CollectivePot → Production → Order
    
    Un Product peut avoir :
    - 0..N Suggestions (plats visibles non financés)
    - 0..N CollectivePots (marmites en financement ou terminées)
    """
    __tablename__ = "products"
    
    # 🔑 Identité
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 📦 Informations produit
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    # 💰 Pricing
    price = Column(Float, nullable=False)
    price_solo = Column(Float, nullable=True)
    price_duo = Column(Float, nullable=True)
    price_family = Column(Float, nullable=True)
    family_size = Column(Integer, nullable=True)
    
    # 🥗 Accompagnements
    complements = Column(String(255), nullable=True)
    
    # 🎯 Hero flag
    is_hero = Column(Boolean, nullable=True)
    
    # 🔗 Relations (Architecture définitive)
    suggestions = relationship(
        "Suggestion",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    daily_offers = relationship(
        "DailyOffer",
        back_populates="product"
    )
    
    # 🧠 Propriété de compatibilité
    @property
    def product_name(self) -> str:
        return self.name
    
    def __repr__(self):
        return f"<Product {self.name} (ID: {self.id})>"