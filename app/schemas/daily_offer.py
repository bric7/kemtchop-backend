# app/schemas/daily_offer.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from uuid import UUID


class ProductSummary(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class DailyOfferResponse(BaseModel):
    id: UUID
    product: ProductSummary
    target_date: date
    status: str
    minimum_threshold: int
    max_capacity: Optional[int] = None
    reserved_portions: int
    current_revenue: float
    price_per_unit: float

    # Propriétés calculées
    progress_percentage: float
    remaining_to_trigger: int
    remaining_capacity: int
    is_threshold_reached: bool

    bonus_description: Optional[str] = None
    triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DailyOfferCreate(BaseModel):
    product_id: int
    target_date: date
    minimum_threshold: int = Field(default=4)
    max_capacity: Optional[int] = None
    price_per_unit: float
    status: Optional[str] = None  # Si None, sera déterminé par la Loi J+1
    bonus_description: Optional[str] = None
    admin_notes: Optional[str] = None
