# app/routes/production.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.entities import DailyOffer
from app.enums import ProductionStatus
from app.auth import check_permission
from app.utils.timezone import get_business_datetime

router = APIRouter(prefix="/production", tags=["Production"])


# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
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


# ============================================================
# 👨‍🍳 ENDPOINTS CUISINE (Production)
# ============================================================

@router.get("/live", response_model=List[ProductionStatusResponse])
def get_live_productions(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Voir toutes les productions en cours (dashboard cuisine)"""
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
            id=p.id,
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
    """✅ Démarrer la cuisine d'une production confirmée"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.CONFIRMED.value:
        raise HTTPException(
            status_code=400, 
            detail=f"Impossible de démarrer : statut actuel = {offer.status}"
        )
    
    offer.status = ProductionStatus.COOKING.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    db.commit()
    
    return {"status": "success", "message": f"Cuisine démarrée pour {offer.product.name}"}


@router.post("/{offer_id}/ready")
def mark_production_ready(
    offer_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Marquer une production comme prête pour livraison"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.COOKING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de marquer prête : statut actuel = {offer.status}"
        )
    
    offer.status = ProductionStatus.READY.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    db.commit()
    
    # TODO: Notifier les livreurs que les commandes sont prêtes
    
    return {"status": "success", "message": f"{offer.product.name} est prêt pour livraison"}


@router.post("/{offer_id}/complete")
def complete_production(
    offer_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Marquer une production comme terminée (toutes les livraisons faites)"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.READY.value:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de terminer : statut actuel = {offer.status}"
        )
    
    offer.status = ProductionStatus.DELIVERED.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    db.commit()
    
    return {"status": "success", "message": f"Production {offer.product.name} terminée"}


@router.post("/{offer_id}/cancel")
def cancel_production(
    offer_id: str,
    action: ProductionAction,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Annuler une production avec remboursement des clients"""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status in [ProductionStatus.DELIVERED.value, ProductionStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible d'annuler : statut actuel = {offer.status}"
        )
    
    old_status = offer.status
    offer.status = ProductionStatus.CANCELLED.value
    offer.admin_override_reason = f"Annulé par admin : {action.reason}"
    offer.updated_at = get_business_datetime().replace(tzinfo=None)
    
    # TODO: Déclencher le remboursement de toutes les commandes liées
    # for order in offer.orders:
    #     order.refund_status = "REFUND_PENDING"
    
    db.commit()
    
    return {
        "status": "success", 
        "message": f"Production annulée ({old_status} → cancelled). Raison : {action.reason}"
    }