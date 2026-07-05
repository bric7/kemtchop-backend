# app/schemas/suggestion.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from uuid import UUID


class RecipeSummary(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class SuggestionResponse(BaseModel):
    id: UUID
    product: RecipeSummary
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


class LaunchMarmiteRequest(BaseModel):
    """Requête pour transformer une Suggestion en CollectivePot"""
    target_date: date
    minimum_orders: int = Field(default=3, ge=1)
    max_orders: Optional[int] = Field(default=None, ge=1)
    preorder_price: float = Field(gt=0)
    discount_percentage: float = Field(default=20.0, ge=0, le=50)
    bonus_description: Optional[str] = None