from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class IngredientBase(BaseModel):
    name: str
    unit: str
    min_threshold: float = 0.0

class IngredientCreate(IngredientBase):
    current_quantity: float = 0.0

class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    min_threshold: Optional[float] = None
    current_quantity: Optional[float] = None

class IngredientResponse(IngredientBase):
    id: int
    current_quantity: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
