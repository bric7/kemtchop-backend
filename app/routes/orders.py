# app/routes/orders.py
# ============================================================
# 📦 ROUTES COMMANDES - KemTchop API (Version Réalignée Production)
# ============================================================

import logging
import uuid
from datetime import datetime, date  # ✅ AJOUT DE 'date' ICI
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session, joinedload

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
from pydantic import BaseModel, Field, ConfigDict

class OrderCreateRequest(BaseModel):
    daily_offer_id: str = Field(..., description="ID de l'offre du jour (UUID)")
    portions: int = Field(1, ge=1, le=10, description="Nombre de portions (1-10)")
    delivery_zone: str = Field(..., min_length=2, max_length=100)
    delivery_date: Optional[str] = Field(None, description="Date de livraison souhaitée (YYYY-MM-DD)")
    delivery_time: Optional[str] = Field(None, description="Heure de livraison souhaitée")
    complement: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, description="Numéro de téléphone du client")
    affiliate_code: Optional[str] = Field(None)

# ✅ AJOUT CRITIQUE : Définition du schéma résumé pour l'offre liée
class DailyOfferSummary(BaseModel):
    id: uuid.UUID
    status: str
    reserved_portions: int
    minimum_threshold: int
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: uuid.UUID
    daily_offer_id: Optional[uuid.UUID] = None
    daily_offer: Optional[DailyOfferSummary] = None  # ✅ Maintenant cela fonctionne
    product_name: Optional[str] = None
    customer_name: str
    phone: str
    zone: Optional[str] = None
    total_amount: float
    portions: int
    complement: Optional[str] = None
    status: str
    delivery_date: Optional[str] = None
    delivery_time: Optional[str] = None
    affiliate_code: Optional[str] = None
    affiliate_payout_phone: Optional[str] = None
    commission_paid: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

# ============================================================
# 📦 ACTIONS COMMANDES (CLIENT)
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
    """✅ Créer une nouvelle commande culinaire avec vérifications strictes"""
    
    # 1. Vérifier l'offre du jour
    offer = db.query(DailyOffer).filter(DailyOffer.id == payload.daily_offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    if not offer.status_enum.is_accepting_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Cette offre n'accepte plus de commandes (statut: {offer.status})"
        )
    
    # 2. ✅ VÉRIFICATION DE CAPACITÉ (Stock restant)
    if offer.remaining_capacity < payload.portions:
        raise HTTPException(
            status_code=400,
            detail=f"Capacité insuffisante : {offer.remaining_capacity} portions restantes (demandé: {payload.portions})"
        )
    
    # 3. ✅ VÉRIFICATION DE L'HEURE LIMITE (Cutoff)
    if offer.target_date == date.today():
        current_hour = datetime.now().hour
        if current_hour >= 10:  # Cutoff à 10h
            raise HTTPException(
                status_code=400,
                detail="Délai de réservation dépassé pour aujourd'hui (cutoff: 10h)"
            )
    
    # 4. Idempotence
    if idempotency_key:
        existing = db.query(Order).filter(Order.idempotency_key == idempotency_key).first()
        if existing:
            return {
                "status": "success",
                "order_id": str(existing.id),
                "duplicate": True,
                "message": "Commande déjà enregistrée"
            }
    
    # 5. Calcul du montant
    total_amount = offer.price_per_unit * payload.portions

    # 6. Sécurisation des informations client
    user_phone = current_user.get("phone")
    customer_name = current_user.get("name")

    if not customer_name:
        db_user = db.query(User).filter(User.phone == user_phone).first()
        customer_name = db_user.customer_name if db_user else None

    if not customer_name:
        customer_name = "Client KemTchop"

    product_name = offer.product.name if (offer.product and offer.product.name) else "Plat du Jour"

    # 7. Création de la commande
    final_delivery_date = payload.delivery_date or (offer.target_date.strftime("%Y-%m-%d") if offer.target_date else "")

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
        delivery_date=final_delivery_date,
        delivery_time=payload.delivery_time,
        idempotency_key=idempotency_key
    )
    
    try:
        db.add(new_order)
        db.flush()
        db.commit()
        db.refresh(new_order)

        logger.info(f"✅ Commande créée : {new_order.id} pour {product_name}")

        return {
            "status": "success",
            "order_id": str(new_order.id),
            "total_amount": total_amount,
            "offer_status": offer.status,
            "message": "Commande enregistrée avec succès"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur création commande : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la commande")


@router.get("/my-orders", response_model=List[OrderResponse])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20
):
    """Récupérer les commandes de l'utilisateur connecté"""
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
    """Récupérer les détails d'une commande spécifique"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    if order.phone != current_user.get("phone") and current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return order


# ============================================================
# 👑 ENDPOINTS ADMIN (Gestion de toutes les commandes)
# ============================================================

@router.get("/admin/orders", response_model=List[OrderResponse])
def get_all_orders_admin(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """Admin : Récupère TOUTES les commandes de tous les clients"""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    
    # On charge aussi la DailyOffer liée pour que le frontend affiche le seuil
    orders = db.query(Order).options(
        joinedload(Order.daily_offer)
    ).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    return orders


@router.patch("/admin/orders/{order_id}/status")
def update_order_status_admin(
    order_id: str,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Admin : Change le statut d'une commande spécifique"""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    # Mapping des statuts du frontend vers les statuts backend (OrderStatus)
    status_mapping = {
        "confirmed": OrderStatus.PAID.value,
        "preparing": OrderStatus.PREPARING.value,
        "ready": OrderStatus.READY_TO_SHIP.value,
        "out_for_delivery": OrderStatus.SHIPPING.value,
        "delivered": OrderStatus.DELIVERED.value,
        "cancelled": OrderStatus.CANCELLED.value
    }
    
    backend_status = status_mapping.get(new_status.lower(), new_status.lower())
    order.status = backend_status
    order.updated_at = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"🔄 Admin a changé le statut de la commande {order_id} vers {backend_status}")
    
    return {"status": "success", "message": f"Statut mis à jour vers {backend_status}"}