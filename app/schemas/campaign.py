# app/schemas/campaign.py
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional


class RecipeSummary(BaseModel):
    """📦 Infos minimales de la recette (VERSION SIMPLIFIÉE)"""
    id: int
    name: str
    category: str
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    """📝 Schéma pour créer une Campaign (admin)"""
    recipe_id: int
    target_date: date
    minimum_orders: int = Field(3, ge=1)
    max_orders: Optional[int] = Field(None, ge=1)
    pack_price: float = Field(..., gt=0)
    early_bird_price: float = Field(..., gt=0)
    standard_price: float = Field(..., gt=0)
    bonus_description: Optional[str] = None
    admin_notes: Optional[str] = None
    
    @field_validator('target_date')
    @classmethod
    def date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError("La date doit être aujourd'hui ou dans le futur")
        return v


class CampaignResponse(BaseModel):
    """📊 Schéma de réponse pour le frontend mobile"""
    id: str
    recipe: RecipeSummary
    target_date: date
    status: str
    minimum_orders: int
    max_orders: Optional[int]
    current_orders: int
    current_revenue: float
    pack_price: float
    early_bird_price: float
    standard_price: float
    display_price: float
    progress_percentage: float
    remaining_to_fund: int
    bonus_description: Optional[str] = None
    is_funded: bool
    is_active: bool
    funded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True