# app/routes/orders.py
# ============================================================
# 📦 ROUTES COMMANDES - KemTchop API (Version Réalignée Production)
# ============================================================

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.daily_offer import DailyOffer
from app.entities.order import Order
from app.entities.product import Product
from app.entities.user import User
from app.enums import ProductionStatus, OrderStatus
from app.auth import get_current_user
from app.services.notification_service import NotificationService

logger = logging.getLogger("kemtchop.orders")
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/orders", tags=["Orders"])

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
from pydantic import BaseModel, Field

class OrderCreateRequest(BaseModel):
    daily_offer_id: str = Field(..., description="ID de l'offre du jour (UUID)")
    portions: int = Field(1, ge=1, le=10, description="Nombre de portions (1-10)")
    delivery_zone: str = Field(..., min_length=2, max_length=100)
    complement: Optional[str] = Field(None, max_length=200)
    affiliate_code: Optional[str] = Field(None)

class OrderResponse(BaseModel):
    id: str
    product_name: Optional[str] = None
    customer_name: str
    phone: str
    zone: Optional[str] = None
    total_amount: float
    portions: int
    status: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================
# 📦 ACTIONS COMMANDES
# ============================================================

@router.post("/create", response_model=dict, status_code=201)
@limiter.limit("30/minute")
async def create_order(
    request: Request,
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: dict = Depends(get_current_user)
):
    """✅ Créer une nouvelle commande culinaire"""
    
    # 1. Vérifier l'offre du jour
    offer = db.query(DailyOffer).filter(
        DailyOffer.id == payload.daily_offer_id
    ).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    if not offer.status_enum.is_accepting_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Cette offre n'accepte plus de commandes (statut: {offer.status})"
        )
    
    # 2. Vérifier la capacité
    if offer.remaining_capacity < payload.portions:
        raise HTTPException(
            status_code=400,
            detail=f"Capacité insuffisante : {offer.remaining_capacity} portions restantes"
        )
    
    # 3. Idempotence
    if idempotency_key:
        existing = db.query(Order).filter(
            Order.idempotency_key == idempotency_key
        ).first()
        if existing:
            return {
                "status": "success",
                "order_id": str(existing.id),
                "duplicate": True,
                "message": "Commande déjà enregistrée"
            }
    
    # 4. Calcul du montant (Prix unique par portion)
    total_amount = offer.price_per_unit * payload.portions

    # 5. Sécurisation des informations client
    user_phone = current_user.get("phone")
    customer_name = current_user.get("name")

    print(f"DEBUG ORDERS: phone={user_phone}, name_in_token={customer_name}")

    if not customer_name:
        db_user = db.query(User).filter(User.phone == user_phone).first()
        customer_name = db_user.customer_name if db_user else None
        print(f"DEBUG ORDERS: name_from_db={customer_name}")

    # Valeur de secours ultime pour éviter le crash NotNull
    if not customer_name:
        customer_name = "Client KemTchop"

    product_name = offer.product.name if (offer.product and offer.product.name) else "Plat du Jour"
    print(f"DEBUG ORDERS: customer_final={customer_name}, product={product_name}")

    # 6. Création de la commande
    new_order = Order(
        daily_offer_id=offer.id,
        customer_name=customer_name,
        phone=user_phone,
        product_name=product_name,
        zone=payload.delivery_zone,
        total_amount=total_amount,
        portions=payload.portions,
        complement=payload.complement,
        affiliate_code=payload.affiliate_code,
        affiliate_payout_phone=user_phone if payload.affiliate_code else None,
        status=OrderStatus.PENDING.value,
        delivery_date=offer.target_date.strftime("%Y-%m-%d") if offer.target_date else "",
        idempotency_key=idempotency_key
    )
    
    try:
        db.add(new_order)
        db.flush()
        
        # Mettre à jour les portions réservées
        offer.reserved_portions += payload.portions
        offer.current_revenue += total_amount
        
        # 🔥 LOGIQUE DE DÉCLENCHEMENT : Passage auto en CONFIRMED si seuil atteint
        if offer.status == ProductionStatus.PROPOSED.value and offer.is_threshold_reached:
            offer.status = ProductionStatus.CONFIRMED.value
            offer.triggered_at = datetime.utcnow()
            logger.info(
                "🚀 Production CONFIRMÉE pour %s : Seuil de %d atteint (%d portions)",
                offer.product.name,
                offer.minimum_threshold,
                offer.reserved_portions
            )
            # 🔔 Notification Seuil Atteint
            await NotificationService.notify_offer_confirmed(
                str(offer.id),
                offer.product.name
            )
        
        db.commit()
        db.refresh(new_order)

        # 🔔 Notification Nouvelle Commande
        await NotificationService.notify_order_created(
            str(new_order.id),
            new_order.customer_name
        )

        return {
            "status": "success",
            "order_id": str(new_order.id),
            "total_amount": total_amount,
            "offer_status": offer.status,
            "message": "Commande enregistrée avec succès"
        }
        
    except Exception as e:
        db.rollback()
        logger.error("❌ Erreur création commande : %s", e)
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la commande")

@router.get("/my-orders", response_model=List[OrderResponse])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20
):
    user_phone = current_user.get("phone")
    orders = db.query(Order).filter(
        Order.phone == user_phone
    ).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    return orders

@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    if order.phone != current_user.get("phone") and current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return order
