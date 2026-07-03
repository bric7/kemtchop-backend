# app/schemas/production.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ProductionAction(BaseModel):
    reason: str = Field(..., min_length=10, description="Raison de l'action (ex: 'Rupture de stock Ndolé')")

class ProductionStatusResponse(BaseModel):
    id: str
    product_name: str
    status: str
    reserved_portions: int
    max_production: Optional[int]
    launched_at: Optional[datetime]
    estimated_ready_time: Optional[str]  # Calculé côté backend
    
    class Config:
        from_attributes = True