# app/schemas/order.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class ReserveOrderRequest(BaseModel):
    daily_menu_id: int = Field(..., gt=0, description="ID du menu du jour")
    portions: int = Field(1, ge=1, le=10, description="Nombre de portions (1-10)")
    delivery_zone: str = Field(..., min_length=2, max_length=100)
    complement: Optional[str] = Field(None, max_length=200)
    affiliate_code: Optional[str] = Field(None, pattern=r'^[A-Z0-9\-]+$')
    
    @field_validator('delivery_zone')
    @classmethod
    def validate_zone(cls, v):
        if v.lower() not in ['bastos', 'akwa', 'bonapriso', 'odza', 'mvan', 'nlongkak', 'elig-edzoa']:
            raise ValueError('Zone de livraison non supportée')
        return v.title()

class ReserveOrderResponse(BaseModel):
    success: bool
    order_id: Optional[int] = None
    remaining_capacity: Optional[int] = None
    message: str
    next_status: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "order_id": 12345,
                "remaining_capacity": 47,
                "message": "Réservation confirmée. 47 places restantes.",
                "next_status": "PRODUCTION_CONFIRMED"
            }
        }