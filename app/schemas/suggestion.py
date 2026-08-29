# app/schemas/suggestion.py
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


class SuggestionResponse(BaseModel):
    id: UUID
    product: ProductSummary
    suggested_date: Optional[datetime] = None
    interest_count: int = 0
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class SuggestionCreate(BaseModel):
    product_id: int
    suggested_date: Optional[date] = None
    notes: Optional[str] = None


class LaunchOfferRequest(BaseModel):
    """Requête pour transformer une Suggestion en DailyOffer"""
    target_date: date
    minimum_threshold: int = Field(default=4, ge=1)
    max_capacity: Optional[int] = Field(default=None, ge=1)
    price_per_unit: float = Field(gt=0)
    bonus_description: Optional[str] = None
