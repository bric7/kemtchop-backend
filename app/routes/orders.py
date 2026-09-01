# app/routes/orders.py
# ============================================================
# 📦 ROUTES COMMANDES - KemTchop API (Version Transactionnelle v3.0 - Lazy Creation)
# ============================================================

import logging
import uuid
from datetime import datetime, date, timedelta, time
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

# ✅ Imports pour la Matrice d'Or et le fuseau horaire
from app.utils.timezone import get_business_date, get_business_datetime, to_business_tz, combine_business_datetime
from app.routes.settings import get_or_create_settings

logger = logging.getLogger("kemtchop.orders")
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/orders", tags=["Orders"])

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
from pydantic import BaseModel, Field, ConfigDict

class OrderCreateRequest(BaseModel):
    product_id: int = Field(..., description="ID du produit")
    target_date: str = Field(..., description="Date cible (YYYY-MM-DD)")
    portions: int = Field(1, ge=1, le=10, description="Nombre de portions (1-10)")
    delivery_zone: str = Field(..., min_length=2, max_length=100)
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
# 📦 CRÉATION DE COMMANDE (CLIENT) — LAZY CREATION + VERROUILLAGE ATOMIQUE
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
    ✅ Créer une commande avec lazy creation de DailyOffer + verrouillage transactionnel.
    
    FLUX :
    1. Vérifier Matrice d'Or (dates, cutoffs)
    2. Chercher DailyOffer(product_id, target_date)
    3. Si existe → utiliser
    4. Si n'existe pas → créer avec paramètres SystemSettings
    5. Vérifier capacité (remaining_capacity >= portions)
    6. Incrémenter reserved_portions
    7. Auto-confirmation si seuil atteint
    8. Créer Order liée
    """
    
    # 🔒 ÉTAPE 0 : LECTURE DES PARAMÈTRES SYSTÈME
    settings = get_or_create_settings(db)
    business_today = get_business_date()
    business_now = get_business_datetime()
    max_days = settings.max_reservation_days
    reservation_cutoff_time = settings.reservation_cutoff_time
    order_cutoff_time = settings.order_cutoff_time
    
    # 🔒 ÉTAPE 1 : VÉRIFICATION MATRICE D'OR (DATE)
    try:
        target = datetime.strptime(payload.target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de date invalide. Utilisez YYYY-MM-DD.")
    
    if target < business_today:
        raise HTTPException(status_code=400, detail="Impossible de commander pour une date passée.")
    
    if target > business_today + timedelta(days=max_days):
        raise HTTPException(status_code=400, detail=f"Les réservations sont limitées à {max_days} jours à l'avance.")
    
    # 🔒 ÉTAPE 2 : VÉRIFICATION PRODUIT
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    if hasattr(product, 'is_active') and not product.is_active:
        raise HTTPException(status_code=400, detail="Ce produit n'est plus disponible")
    
    # 🔒 ÉTAPE 3 : RECHERCHE / CRÉATION DE LA DAILYOFFER (TRANSACTION VERROUILLÉE)
    offer = db.query(DailyOffer).with_for_update().filter(
        DailyOffer.product_id == payload.product_id,
        DailyOffer.target_date == target
    ).first()
    
    if not offer:
        # ✅ LAZY CREATION : Créer la DailyOffer avec les paramètres système
        reservation_cutoff_at = combine_business_datetime(target - timedelta(days=1), reservation_cutoff_time)
        order_cutoff_at = combine_business_datetime(target, order_cutoff_time)
        
        offer = DailyOffer(
            product_id=payload.product_id,
            target_date=target,
            minimum_threshold=4,
            max_capacity=20,
            price_per_unit=float(product.price) if product.price else 2500.0,
            status=ProductionStatus.PROPOSED.value,
            reserved_portions=0,
            reservation_cutoff_at=reservation_cutoff_at,
            order_cutoff_at=order_cutoff_at,
        )
        db.add(offer)
        db.flush()  # Génère l'ID pour la suite de la transaction
        logger.info(f"🆕 DailyOffer créée à la volée : {product.name} pour le {target}")
    
    # 🔒 ÉTAPE 4 : VÉRIFICATION DU CUTOFF ET DU STATUT
    if target == business_today:
        # J+0 : Uniquement si CONFIRMED (Menu du Jour)
        if offer.status != ProductionStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=400,
                detail="Ce plat n'est pas au Menu du Jour aujourd'hui."
            )
        if offer.order_cutoff_at and business_now > to_business_tz(offer.order_cutoff_at):
            raise HTTPException(status_code=400, detail="Le délai de commande pour aujourd'hui est dépassé.")
    else:
        # J+1 à J+7 : Vérifier cutoff de réservation
        if offer.reservation_cutoff_at and business_now > to_business_tz(offer.reservation_cutoff_at):
            raise HTTPException(status_code=400, detail="Le délai de réservation pour cette date est dépassé.")
            
        if offer.status not in [ProductionStatus.PROPOSED.value, ProductionStatus.RESERVATION.value, ProductionStatus.CONFIRMED.value]:
            raise HTTPException(status_code=400, detail=f"Cette offre n'accepte plus de réservations (statut: {offer.status}).")
    
    # 🔒 ÉTAPE 5 : VÉRIFICATION DE CAPACITÉ (remaining_capacity >= portions)
    if offer.reserved_portions + payload.portions > offer.max_capacity:
        remaining = offer.max_capacity - offer.reserved_portions
        raise HTTPException(
            status_code=400,
            detail=f"Capacité maximale atteinte. Il ne reste que {remaining} portion(s) disponible(s)."
        )
    
    # ÉTAPE 6 : IDEMPOTENCE
    if idempotency_key:
        existing = db.query(Order).filter(Order.idempotency_key == idempotency_key).first()
        if existing:
            return {
                "status": "success",
                "order_id": str(existing.id),
                "duplicate": True,
                "message": "Commande déjà enregistrée"
            }
    
    # ÉTAPE 7 : CALCUL DU MONTANT
    total_amount = offer.price_per_unit * payload.portions
    
    # ÉTAPE 8 : INFOS CLIENT
    user_phone = current_user.get("phone")
    customer_name = current_user.get("name")
    
    if not customer_name:
        db_user = db.query(User).filter(User.phone == user_phone).first()
        customer_name = db_user.customer_name if db_user else None
    
    if not customer_name:
        customer_name = "Client KemTchop"
    
    # ÉTAPE 9 : CRÉATION DE LA COMMANDE
    final_delivery_date = payload.target_date  # On utilise la date cible comme date de livraison par défaut
    
    new_order = Order(
        daily_offer_id=offer.id,
        customer_name=customer_name,
        phone=user_phone,
        product_name=product.name,
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
        
        # 🔒 ÉTAPE 10 : INCRÉMENTATION ATOMIQUE
        offer.reserved_portions += payload.portions
        
        # 🔒 ÉTAPE 11 : AUTO-CONFIRMATION SI SEUIL ATTEINT
        if (offer.reserved_portions >= offer.minimum_threshold 
            and offer.status == ProductionStatus.PROPOSED.value):
            offer.status = ProductionStatus.CONFIRMED.value
            offer.triggered_at = get_business_datetime().replace(tzinfo=None)
            offer.triggered_by_admin = False
            logger.info(
                f"🚀 SEUIL ATTEINT AUTO : {product.name} pour le {target} "
                f"({offer.reserved_portions}/{offer.minimum_threshold}) → CONFIRMED"
            )
        
        # 🔒 ÉTAPE 12 : COMMIT ATOMIQUE
        db.commit()
        db.refresh(new_order)
        
        logger.info(f"✅ Commande créée : {new_order.id} pour {product.name} ({payload.portions} portions) le {target}")
        
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
    order.updated_at = get_business_datetime().replace(tzinfo=None)
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
    
    if offer.status not in [ProductionStatus.PROPOSED.value, ProductionStatus.RESERVATION.value]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cette offre est déjà en statut '{offer.status}'. Seules les offres en attente peuvent être forcées."
        )
    
    # Forçage admin
    offer.status = ProductionStatus.CONFIRMED.value
    offer.triggered_at = get_business_datetime().replace(tzinfo=None)
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


@router.post("/admin/cancel-offer/{offer_id}")
def cancel_offer_and_refund(
    offer_id: str,
    payload: dict, # Attend {"reason": "string"}
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    ✅ Annule une DailyOffer et marque toutes les commandes associées pour remboursement.
    """
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé")
    
    reason = payload.get("reason", "Annulation administrative")
    
    # 1. Verrouiller et annuler l'offre
    offer = db.query(DailyOffer).with_for_update().filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
        
    if offer.status in [ProductionStatus.CANCELLED.value, ProductionStatus.DELIVERED.value]:
        raise HTTPException(status_code=400, detail="Cette offre ne peut plus être annulée.")

    old_status = offer.status
    offer.status = ProductionStatus.CANCELLED.value
    offer.admin_override_reason = f"Annulé: {reason}"
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # 2. Trouver les commandes actives liées à cette offre
    from app.entities.order import Order
    from app.enums import OrderStatus
    
    active_statuses = [OrderStatus.PENDING.value, OrderStatus.PAID.value, OrderStatus.PREPARING.value]
    
    # Mise à jour en masse (Bulk update) pour la performance et la sécurité transactionnelle
    updated_count = db.query(Order).filter(
        Order.daily_offer_id == offer_id,
        Order.status.in_(active_statuses)
    ).update({
        "status": OrderStatus.CANCELLED.value,
        "refund_status": "REFUND_PENDING",
        "cancellation_reason": f"OFFER_CANCELLED: {reason}",
        "cancelled_at": get_business_datetime().replace(tzinfo=None),
        "refund_amount": Order.deposit_amount # On rembourse l'acompte
    }, synchronize_session=False)
    
    db.commit()
    
    logger.warning(
        f"🚫 OFFRE ANNULÉE : {offer.product.name} ({old_status} -> CANCELLED). "
        f"{updated_count} commande(s) marquées pour remboursement."
    )
    
    # TODO: Déclencher ici l'envoi de SMS/WhatsApp de masse aux clients concernés
    
    return {
        "status": "success",
        "message": f"Offre annulée. {updated_count} client(s) seront remboursés.",
        "refunded_orders_count": updated_count
    }