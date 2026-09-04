from pydantic import BaseModel
from typing import List, Optional

class ProductIngredientBase(BaseModel):
    ingredient_id: int
    quantity_per_portion: float

class ProductIngredientCreate(ProductIngredientBase):
    pass

class ProductIngredientResponse(ProductIngredientBase):
    id: int
    ingredient_name: Optional[str] = None
    ingredient_unit: Optional[str] = None

    class Config:
        from_attributes = True

class RecipeUpdate(BaseModel):
    ingredients: List[ProductIngredientCreate]
