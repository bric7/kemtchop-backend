# app/schemas/daily_menu.py
from pydantic import BaseModel, Field, field_validator
from datetime import date, time, datetime
from typing import Optional
from enum import Enum

# Si tu n'as pas encore app/enums.py, définis l'enum ici temporairement
class ProductionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CONFIRMED = "confirmed"
    COOKING = "cooking"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

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

class ProductSummary(BaseModel):
    id: int
    name: str
    category: str
    image_url: Optional[str] = None
    class Config:
        from_attributes = True

class DailyMenuResponse(BaseModel):
    id: str
    product: ProductSummary
    occurrence_date: date
    cutoff_time: time
    status: str
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