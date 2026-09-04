from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base

class Ingredient(Base):
    """
    🥗 Ingredient = Matière première utilisée en cuisine.
    Exemple : Poulet, Huile de palme, Riz, Sel.
    """
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    unit = Column(String(50), nullable=False)  # kg, g, l, ml, piece, sac

    # Seuil d'alerte pour le stock bas
    min_threshold = Column(Float, default=0.0)

    # Quantité actuelle en stock
    current_quantity = Column(Float, default=0.0, nullable=False)

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Ingredient {self.name} ({self.unit})>"
