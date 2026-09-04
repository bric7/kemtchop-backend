from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class StockMovement(Base):
    """
    📉 StockMovement = Historique des entrées/sorties de stock.
    Types : PURCHASE (achat), COOKING (consommation), WASTE (perte), ADJUSTMENT (inventaire).
    """
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)

    quantity = Column(Float, nullable=False)  # Positif pour entrée, négatif pour sortie
    movement_type = Column(String(50), nullable=False)  # PURCHASE, COOKING, WASTE, ADJUSTMENT

    reference_id = Column(String(100), nullable=True)  # ID de Production ou numéro de facture
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    ingredient = relationship("Ingredient")

    def __repr__(self):
        return f"<StockMovement {self.movement_type}: {self.quantity} for ingredient {self.ingredient_id}>"
