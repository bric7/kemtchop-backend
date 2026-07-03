# app/schemas/daily_menu.py
from pydantic import BaseModel, Field, field_validator
from datetime import date, time, datetime
from typing import Optional, List
from enum import Enum

class DailyMenuStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PREORDER_OPEN = "PREORDER_OPEN"
    PRODUCTION_CONFIRMED = "PRODUCTION_CONFIRMED"
    PRODUCTION_CLOSED = "PRODUCTION_CLOSED"
    DELIVERED = "DELIVERED"

class DailyMenuCreate(BaseModel):
    product_id: int
    occurrence_date: date
    cutoff_time: Optional[time] = None
    minimum_production: int = Field(3, ge=1)
    max_production: Optional[int] = Field(None, ge=1)
    pack_price: float = Field(..., gt=0)
    individual_price: float = Field(..., gt=0)
    bonus_description: Optional[str] = None
    notes: Optional[str] = None
    
    @field_validator('occurrence_date')
    @classmethod
    def date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError("La date doit être aujourd'hui ou dans le futur")
        return v

class DailyMenuUpdate(BaseModel):
    status: Optional[DailyMenuStatus] = None
    cutoff_time: Optional[time] = None
    max_production: Optional[int] = None
    bonus_description: Optional[str] = None
    notes: Optional[str] = None

# ✅ CORRECTION : Définition de ProductSummary (ou importe-le depuis product.py)
class ProductSummary(BaseModel):
    id: int  # ← INTEGER pour matcher products.id
    name: str
    category: str
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True

class DailyMenuResponse(BaseModel):
    id: str
    product: ProductSummary  # ← Maintenant défini ✅
    occurrence_date: date
    cutoff_time: time
    status: DailyMenuStatus
    minimum_production: int
    max_production: Optional[int]
    reserved_portions: int
    pack_price: float
    individual_price: float
    bonus_description: Optional[str]
    remaining_capacity: Optional[int] = None
    progress_percentage: float = 0.0
    launched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DailyMenuBase(BaseModel):
    product_id: str  # Représente l'ID de la recette dans ta table des produits actuel
    occurrence_date: date
    cutoff_time: Optional[str] = "18:00:00"
    minimum_production: Optional[int] = 3
    max_production: Optional[int] = 25
    is_hero: Optional[bool] = False  # 🔥 Ajouté pour le feed immersif du mobile

class DailyMenuCreate(DailyMenuBase):
    pass

class DailyMenuResponse(DailyMenuBase):
    id: str
    status: str
    reserved_portions: int

    class Config:
        from_attributes = True