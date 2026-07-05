# app/schemas/collective_pot.py
from pydantic import BaseModel
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


class CollectivePotResponse(BaseModel):
    id: UUID
    recipe: RecipeSummary
    target_date: date
    status: str
    minimum_orders: int
    max_orders: Optional[int] = None
    current_orders: int
    current_revenue: float
    preorder_price: float
    live_price: float
    sponsor_pack_price: float
    discount_percentage: float
    display_price: float
    progress_percentage: float
    remaining_to_fund: int
    remaining_capacity: int
    remaining_amount: float
    bonus_description: Optional[str] = None
    is_funded: bool
    is_active: bool
    funded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True