# app/schemas/campaign.py
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Optional


class RecipeSummary(BaseModel):
    """📦 Infos minimales de la recette"""
    id: int
    name: str
    category: str
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    """
    📝 Schéma SIMPLIFIÉ pour créer une Campaign
    L'admin ne saisit que 3 champs :
    - standard_price (prix normal par portion)
    - minimum_orders (seuil de lancement)
    - discount_percentage (réduction après lancement)
    
    Le backend calcule automatiquement :
    - pack_price = standard_price × minimum_orders
    - early_bird_price = standard_price × (1 - discount_percentage/100)
    """
    recipe_id: int
    target_date: date
    minimum_orders: int = Field(3, ge=1, description="Seuil de lancement")
    max_orders: Optional[int] = Field(None, ge=1, description="Capacité max")
    
    # ✅ ADMIN SAISIT SEULEMENT CES 3 CHAMPS
    standard_price: float = Field(..., gt=0, description="Prix normal par portion")
    discount_percentage: float = Field(20.0, ge=0, le=50, description="Réduction % après lancement (0-50%)")
    
    bonus_description: Optional[str] = None
    admin_notes: Optional[str] = None
    
    # ✅ Ces champs sont calculés automatiquement
    pack_price: Optional[float] = Field(None, description="Calculé: standard_price × minimum_orders")
    early_bird_price: Optional[float] = Field(None, description="Calculé: standard_price × (1 - discount%)")
    
    @field_validator('target_date')
    @classmethod
    def date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError("La date doit être aujourd'hui ou dans le futur")
        return v
    
    @model_validator(mode='after')
    def calculate_prices(self):
        """✅ Calcul automatique des prix"""
        # Pack price = prix normal × nombre minimum de commandes
        self.pack_price = round(self.standard_price * self.minimum_orders, 2)
        
        # Early bird = prix normal avec réduction
        self.early_bird_price = round(
            self.standard_price * (1 - self.discount_percentage / 100), 
            2
        )
        
        return self


class CampaignResponse(BaseModel):
    """📊 Schéma de réponse avec nouvelles informations"""
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
    discount_percentage: float  # ✅ NOUVEAU
    display_price: float
    progress_percentage: float
    remaining_to_fund: int
    remaining_amount: float  # ✅ NOUVEAU : "Encore X FCFA"
    bonus_description: Optional[str] = None
    is_funded: bool
    is_active: bool
    funded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True