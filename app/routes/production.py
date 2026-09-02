# app/routes/production.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.entities import DailyOffer, Order
from app.enums import ProductionStatus, OrderStatus
from app.auth import check_permission
from app.utils.timezone import get_business_datetime
import logging

logger = logging.getLogger("kemtchop.production")
router = APIRouter(prefix="/production", tags=["Production"])

class ProductionStatusResponse(BaseModel):
    id: str
    product_name: str
    target_date: str
    status: str
    reserved_portions: int
    minimum_threshold: int
    max_capacity: int
    triggered_at: Optional[str] = None
    
    class Config:
        from_attributes = True

class ProductionAction(BaseModel):
    reason: str

@router.get("/live", response_model=List[ProductionStatusResponse])
def get_live_productions(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """Voir toutes les productions en cours"""
    productions = db.query(DailyOffer).filter(
        DailyOffer.status.in_([
            ProductionStatus.CONFIRMED.value,
            ProductionStatus.COOKING.value,
            ProductionStatus.READY.value,
        ])
    ).all()
    
    result = []
    for p in productions:
        result.append(ProductionStatusResponse(
            id=str(p.id),
            product_name=p.product.name if p.product else "Inconnu",
            target_date=str(p.target_date),
            status=p.status,
            reserved_portions=p.reserved_portions,
            minimum_threshold=p.minimum_threshold,
            max_capacity=p.max_capacity,
            triggered_at=p.triggered_at.isoformat() if p.triggered_at else None,
        ))
    return result

@router.post("/{offer_id}/start")
def start_production(
    offer_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """Démarrer la cuisine d'une production confirmée"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.COOKING.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # ✅ CORRECTION : Mettre à jour les commandes de manière robuste
    # On cherche les commandes payées OU en attente (au cas où le paiement n'a pas été marqué)
    orders_to_update = db.query(Order).filter(
        Order.daily_offer_id == offer_id,
        Order.status.in_([OrderStatus.PAID.value, OrderStatus.PENDING.value])
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.PREPARING.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
        logger.info(f"🔄 Commande {order.id} passée à PREPARING")
    
    db.commit()
    
    logger.info(f"✅ Cuisine démarrée pour {offer.product.name if offer.product else 'plat'}. {updated_count} commande(s) mise(s) à jour.")
    return {
        "status": "success", 
        "message": f"Cuisine démarrée. {updated_count} commande(s) mise(s) en préparation.",
        "updated_orders": updated_count
    }

@router.post("/{offer_id}/ready")
def mark_production_ready(
    offer_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """Marquer une production comme prête pour livraison"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.COOKING.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.READY.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # ✅ CORRECTION : Mettre à jour les commandes en préparation
    orders_to_update = db.query(Order).filter(
        Order.daily_offer_id == offer_id,
        Order.status == OrderStatus.PREPARING.value
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.READY_TO_SHIP.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
        logger.info(f"🔄 Commande {order.id} passée à READY_TO_SHIP")
    
    db.commit()
    
    logger.info(f"✅ Production prête. {updated_count} commande(s) prête(s) à expédier.")
    return {
        "status": "success", 
        "message": f"{offer.product.name if offer.product else 'Plat'} prêt. {updated_count} commande(s) prête(s).",
        "updated_orders": updated_count
    }

@router.post("/{offer_id}/delivering")
def mark_production_delivering(
    offer_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """Marquer une production comme en cours de livraison"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.READY.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.DELIVERING.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # ✅ CORRECTION : Mettre à jour les commandes prêtes à expédier
    orders_to_update = db.query(Order).filter(
        Order.daily_offer_id == offer_id,
        Order.status == OrderStatus.READY_TO_SHIP.value
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.SHIPPING.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
        logger.info(f"🔄 Commande {order.id} passée à SHIPPING")
    
    db.commit()
    
    logger.info(f"✅ En livraison. {updated_count} commande(s) expédiée(s).")
    return {
        "status": "success", 
        "message": f"En cours de livraison. {updated_count} commande(s) expédiée(s).",
        "updated_orders": updated_count
    }

@router.post("/{offer_id}/complete")
def complete_production(
    offer_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """Marquer une production comme terminée"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.DELIVERING.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.DELIVERED.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # ✅ CORRECTION : Mettre à jour les commandes en livraison
    orders_to_update = db.query(Order).filter(
        Order.daily_offer_id == offer_id,
        Order.status == OrderStatus.SHIPPING.value
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.DELIVERED.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
        logger.info(f"🔄 Commande {order.id} passée à DELIVERED")
    
    db.commit()
    
    logger.info(f"✅ Production terminée. {updated_count} commande(s) livrée(s).")
    return {
        "status": "success", 
        "message": f"Production terminée. {updated_count} commande(s) livrée(s).",
        "updated_orders": updated_count
    }

@router.post("/{offer_id}/cancel")
def cancel_production(
    offer_id: str,
    action: ProductionAction,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """Annuler une production avec remboursement des clients"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status in [ProductionStatus.DELIVERED.value, ProductionStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail=f"Impossible d'annuler : statut actuel = {offer.status}")
    
    old_status = offer.status
    offer.status = ProductionStatus.CANCELLED.value
    offer.admin_override_reason = f"Annulé par admin : {action.reason}"
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # Annuler les commandes actives
    active_statuses = [
        OrderStatus.PENDING.value,
        OrderStatus.PAID.value,
        OrderStatus.PREPARING.value,
        OrderStatus.READY_TO_SHIP.value,
        OrderStatus.SHIPPING.value
    ]
    
    orders_to_cancel = db.query(Order).filter(
        Order.daily_offer_id == offer_id,
        Order.status.in_(active_statuses)
    ).all()
    
    cancelled_count = 0
    for order in orders_to_cancel:
        order.status = OrderStatus.CANCELLED.value
        order.refund_status = "REFUND_PENDING"
        order.cancellation_reason = f"Production annulée: {action.reason}"
        order.cancelled_at = get_business_datetime().replace(tzinfo=None)
        order.refund_amount = order.deposit_amount
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        cancelled_count += 1
    
    db.commit()
    
    logger.warning(f"🚫 Production annulée ({old_status} → CANCELLED). {cancelled_count} commande(s) annulée(s).")
    return {
        "status": "success", 
        "message": f"Production annulée. {cancelled_count} commande(s) marquée(s) pour remboursement.",
        "cancelled_orders": cancelled_count
    }