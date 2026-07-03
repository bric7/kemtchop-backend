# app/schemas/daily_menu.py
from pydantic import BaseModel, Field, field_validator
from datetime import date, time
from typing import Optional, List
from enum import Enum
from datetime import date, time, datetime 

class DailyMenuStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PREORDER_OPEN = "PREORDER_OPEN"
    PRODUCTION_CONFIRMED = "PRODUCTION_CONFIRMED"
    PRODUCTION_CLOSED = "PRODUCTION_CLOSED"
    DELIVERED = "DELIVERED"

class DailyMenuCreate(BaseModel):
    product_id: str
    occurrence_date: date
    cutoff_time: Optional[time] = None
    minimum_production: Optional[int] = Field(3, ge=1)
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

class DailyMenuResponse(BaseModel):
    id: str
    product: "ProductSummary"  # Nested schema
    occurrence_date: date
    cutoff_time: time
    status: DailyMenuStatus
    minimum_production: int
    max_production: Optional[int]
    reserved_portions: int
    pack_price: float
    individual_price: float
    bonus_description: Optional[str]
    remaining_capacity: Optional[int]
    progress_percentage: float
    launched_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ProductSummary(BaseModel):
    id: str
    name: str
    category: str
    image_url: Optional[str]
    
    class Config:
        from_attributes = True