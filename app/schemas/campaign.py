# app/schemas/campaign.py
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Optional


# ✅ RENOMMÉ : RecipeSummary → ProductSummary (cohérent avec l'architecture)
class ProductSummary(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    recipe_id: int
    target_date: date
    minimum_orders: int = Field(3, ge=1)
    max_orders: Optional[int] = Field(None, ge=1)
    preorder_price: float = Field(..., gt=0)
    discount_percentage: float = Field(20.0, ge=0, le=50)
    bonus_description: Optional[str] = None
    admin_notes: Optional[str] = None
    sponsor_pack_price: Optional[float] = None
    live_price: Optional[float] = None

    @field_validator('target_date')
    @classmethod
    def date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError("La date doit être aujourd'hui ou dans le futur")
        return v

    @model_validator(mode='after')
    def calculate_prices(self):
        self.sponsor_pack_price = round(self.preorder_price * self.minimum_orders, 2)
        self.live_price = round(self.preorder_price * (1 - self.discount_percentage / 100), 2)
        return self


class CampaignResponse(BaseModel):
    id: str
    # ✅ CORRIGÉ : recipe → product
    product: ProductSummary
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