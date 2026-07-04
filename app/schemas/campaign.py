# app/schemas/campaign.py
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Optional


class RecipeSummary(BaseModel):
    """📦 Infos minimales de la recette pour le frontend"""
    id: int
    name: str
    category: str
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    """
    📝 Schéma SIMPLIFIÉ pour créer une Campaign
    
    L'admin saisit seulement 3 champs :
    - preorder_price (prix normal par portion)
    - minimum_orders (seuil de lancement)
    - discount_percentage (réduction après lancement)
    
    Le backend calcule automatiquement :
    - sponsor_pack_price = preorder_price × minimum_orders
    - live_price = preorder_price × (1 - discount_percentage/100)
    """
    recipe_id: int
    target_date: date
    minimum_orders: int = Field(3, ge=1, description="Seuil de lancement")
    max_orders: Optional[int] = Field(None, ge=1, description="Capacité max")
    
    # ✅ ADMIN SAISIT SEULEMENT CES 3 CHAMPS
    preorder_price: float = Field(..., gt=0, description="Prix normal par portion (avant seuil)")
    discount_percentage: float = Field(
        20.0, 
        ge=0, 
        le=50, 
        description="Réduction % après lancement (0-50%)"
    )
    
    bonus_description: Optional[str] = None
    admin_notes: Optional[str] = None
    
    # ✅ Ces champs sont calculés automatiquement
    sponsor_pack_price: Optional[float] = Field(
        None, 
        description="Calculé: preorder_price × minimum_orders"
    )
    live_price: Optional[float] = Field(
        None, 
        description="Calculé: preorder_price × (1 - discount%)"
    )
    
    @field_validator('target_date')
    @classmethod
    def date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError("La date doit être aujourd'hui ou dans le futur")
        return v
    
    @model_validator(mode='after')
    def calculate_prices(self):
        """✅ Calcul automatique des prix business"""
        # Sponsor pack = prix normal × nombre minimum de commandes
        self.sponsor_pack_price = round(
            self.preorder_price * self.minimum_orders, 
            2
        )
        
        # Live price = prix normal avec réduction
        self.live_price = round(
            self.preorder_price * (1 - self.discount_percentage / 100), 
            2
        )
        
        return self


class CampaignResponse(BaseModel):
    """📊 Schéma de réponse pour le frontend (mobile + admin)"""
    id: str
    recipe: RecipeSummary
    target_date: date
    status: str
    minimum_orders: int
    max_orders: Optional[int]
    current_orders: int
    current_revenue: float
    
    # 💰 Pricing business (noms clairs)
    preorder_price: float          # Prix avant seuil
    live_price: float              # Prix après seuil
    sponsor_pack_price: float      # Prix pour financer toute la marmite
    discount_percentage: float     # Réduction appliquée
    
    # 📊 Affichage dynamique
    display_price: float           # Prix actuellement affiché au client
    progress_percentage: float     # 0-100%
    remaining_to_fund: int         # Portions restantes
    remaining_capacity: int        # Places avant saturation
    remaining_amount: float        # Montant restant (FCFA)
    
    # 🎁 Bonus
    bonus_description: Optional[str] = None
    
    # 🔄 État
    is_funded: bool
    is_active: bool
    funded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True