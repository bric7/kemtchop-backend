from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ProductIngredient(Base):
    """
    📜 ProductIngredient = Table d'association pour les recettes.
    Définit la quantité d'un ingrédient nécessaire pour 1 portion d'un produit.
    """
    __tablename__ = "product_ingredients"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)

    # Quantité nécessaire par portion
    quantity_per_portion = Column(Float, nullable=False)

    # Relations
    product = relationship("Product", back_populates="recipe_ingredients")
    ingredient = relationship("Ingredient")

    def __repr__(self):
        return f"<Recipe {self.product_id} needs {self.quantity_per_portion} of ingredient {self.ingredient_id}>"
