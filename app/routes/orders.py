# app/routes/orders.py
# ============================================================
# 📦 ROUTES COMMANDES - KemTchop API (Version Transactionnelle v3.0)
# ============================================================

import logging
import uuid
from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
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
    daily_offer_id: str = Field(..., description="ID de l'offre (UUID)")
    portions: int = Field(1, ge=1, le=10, description="Nombre de portions (1-10)")
    delivery_zone: str = Field(..., min_length=2, max_length=100)
    delivery_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    delivery_time: Optional[str] = Field(None)
    complement: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None)
    affiliate_code: Optional[str] = Field(None)

class DailyOfferSummary(BaseModel):
    id: uuid.UUID
    status: str
    reserved_portions: int
    minimum_threshold: int
    max_capacity: int
    target_date: Optional[date] = None
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: uuid.UUID
    daily_offer_id: Optional[uuid.UUID] = None
    daily_offer: Optional[DailyOfferSummary] = None
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
# 📦 CRÉATION DE COMMANDE (CLIENT) — VERROUILLAGE ATOMIQUE
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
    """
    ✅ Créer une commande avec verrouillage transactionnel strict.
    
    RÈGLES MÉTIER VERROUILLÉES :
    - Le verrou with_for_update() empêche les race conditions.
    - reserved_portions + nouvelles portions <= max_capacity (sinon refus).
    - Si reserved_portions >= minimum_threshold → déclenchement automatique CONFIRMED.
    - Un seul client peut déclencher la production à lui seul (ex: 4/4 en une commande).
    """
    
    # 🔒 ÉTAPE 1 : VERROUILLAGE EXCLUSIF DE LA LIGNE DAILYOFFER
    # with_for_update() = SELECT ... FOR UPDATE en SQL
    # Cela bloque toute autre transaction concurrente sur cette ligne
    # jusqu'à ce que notre COMMIT ou ROLLBACK soit exécuté.
    offer = db.query(DailyOffer).with_for_update().filter(
        DailyOffer.id == payload.daily_offer_id
    ).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    # Vérifier que l'offre accepte encore des commandes
    if not offer.status_enum.is_accepting_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Cette offre n'accepte plus de commandes (statut: {offer.status})"
        )
    
    # 🔒 ÉTAPE 2 : VÉRIFICATION ATOMIQUE DE LA CAPACITÉ MAXIMALE
    # Grâce au verrou, aucun autre client ne peut modifier reserved_portions
    # entre notre lecture et notre écriture.
    if offer.reserved_portions + payload.portions > offer.max_capacity:
        remaining = offer.max_capacity - offer.reserved_portions
        raise HTTPException(
            status_code=400,
            detail=f"Capacité maximale atteinte. Il ne reste que {remaining} portion(s) disponible(s)."
        )
    
    # 🔒 ÉTAPE 3 : VÉRIFICATION DE L'HEURE LIMITE (Cutoff J+0)
    if offer.target_date == date.today():
        current_hour = datetime.now().hour
        if current_hour >= 10:
            raise HTTPException(
                status_code=400,
                detail="Délai de réservation dépassé pour aujourd'hui (cutoff: 10h)"
            )
    
    # ÉTAPE 4 : Idempotence (éviter les doublons)
    if idempotency_key:
        existing = db.query(Order).filter(Order.idempotency_key == idempotency_key).first()
        if existing:
            return {
                "status": "success",
                "order_id": str(existing.id),
                "duplicate": True,
                "message": "Commande déjà enregistrée"
            }
    
    # ÉTAPE 5 : Calcul du montant
    total_amount = offer.price_per_unit * payload.portions

    # ÉTAPE 6 : Sécurisation des informations client
    user_phone = current_user.get("phone")
    customer_name = current_user.get("name")

    if not customer_name:
        db_user = db.query(User).filter(User.phone == user_phone).first()
        customer_name = db_user.customer_name if db_user else None

    if not customer_name:
        customer_name = "Client KemTchop"

    product_name = offer.product.name if (offer.product and offer.product.name) else "Plat du Jour"

    # ÉTAPE 7 : Création de la commande
    final_delivery_date = payload.delivery_date or (
        offer.target_date.strftime("%Y-%m-%d") if offer.target_date else ""
    )

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
        
        # 🔒 ÉTAPE 8 : INCRÉMENTATION ATOMIQUE DES PORTIONS ENGAGÉES
        # Cette ligne est protégée par le verrou with_for_update().
        # Même si 10 clients cliquent en même temps, PostgreSQL les traite un par un.
        offer.reserved_portions += payload.portions
        
        # 🔒 ÉTAPE 9 : DÉCLENCHEMENT AUTOMATIQUE DU SEUIL (Règle métier #1)
        # Un seul client peut déclencher la production (ex: 4 portions d'un coup).
        if (offer.reserved_portions >= offer.minimum_threshold 
            and offer.status == ProductionStatus.PROPOSED.value):
            offer.status = ProductionStatus.CONFIRMED.value
            offer.triggered_at = datetime.utcnow()
            offer.triggered_by_admin = False
            logger.info(
                f"🚀 SEUIL ATTEINT PAR COMMANDE CLIENT : "
                f"{product_name} pour le {offer.target_date} "
                f"({offer.reserved_portions}/{offer.minimum_threshold}) → CONFIRMED"
            )
        
        # 🔒 ÉTAPE 10 : COMMIT ATOMIQUE
        # Le verrou est libéré uniquement ici. Toutes les modifications
        # (order + reserved_portions + status) sont écrites en un seul bloc.
        db.commit()
        db.refresh(new_order)

        logger.info(f"✅ Commande créée : {new_order.id} pour {product_name} ({payload.portions} portions)")

        return {
            "status": "success",
            "order_id": str(new_order.id),
            "total_amount": total_amount,
            "offer_status": offer.status,
            "message": "Commande enregistrée avec succès"
        }
        
    except Exception as e:
        db.rollback()  # Le verrou est libéré, aucune donnée corrompue
        logger.error(f"❌ Erreur création commande : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la commande")


# ============================================================
# 📱 COMMANDES CLIENT
# ============================================================

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
# 👑 ENDPOINTS ADMIN
# ============================================================

@router.get("/admin/orders", response_model=List[OrderResponse])
def get_all_orders_admin(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """Admin : Récupère TOUTES les commandes"""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    
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
    """Admin : Change le statut d'une commande"""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
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
    
    logger.info(f"🔄 Admin a changé le statut de la commande {order_id} → {backend_status}")
    return {"status": "success", "message": f"Statut mis à jour vers {backend_status}"}


@router.post("/admin/force-confirm/{offer_id}")
def force_confirm_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Admin : Force le déclenchement d'une DailyOffer même si le seuil n'est pas atteint.
    Permet le déclenchement pour J+0 (aujourd'hui).
    """
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    
    # Verrouillage pour cohérence
    offer = db.query(DailyOffer).with_for_update().filter(
        DailyOffer.id == offer_id
    ).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    if offer.status != ProductionStatus.PROPOSED.value:
        raise HTTPException(
            status_code=400, 
            detail=f"Cette offre est déjà en statut '{offer.status}'. Seul 'proposed' peut être forcé."
        )
    
    # Forçage admin
    offer.status = ProductionStatus.CONFIRMED.value
    offer.triggered_at = datetime.utcnow()
    offer.triggered_by_admin = True
    offer.admin_override_reason = f"Forcé par admin {current_user.get('name', 'inconnu')}"
    
    db.commit()
    
    logger.warning(
        f"⚠️ DÉCLENCHEMENT FORCÉ PAR ADMIN : "
        f"{offer.product.name if offer.product else 'Plat'} "
        f"pour le {offer.target_date} "
        f"({offer.reserved_portions}/{offer.minimum_threshold} portions)"
    )
    
    return {
        "status": "success",
        "message": f"Production forcée pour le {offer.target_date}. Statut: CONFIRMED.",
        "triggered_by_admin": True
    }