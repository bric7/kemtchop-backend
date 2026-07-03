# app/routes/production.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.entities.daily_menu import DailyMenu, DailyMenuStatus
from app.schemas.production import ProductionAction, ProductionStatusResponse
from app.auth import check_permission
from app.services.production_orchestrator import ProductionOrchestrator

router = APIRouter(prefix="/production", tags=["Production"])

@router.get("/live", response_model=List[ProductionStatusResponse])
def get_live_productions(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("production"))
):
    """✅ Voir toutes les productions en cours (dashboard cuisine)"""
    return db.query(DailyMenu).filter(
        DailyMenu.status.in_([
            DailyMenuStatus.PRODUCTION_CONFIRMED,
            DailyMenuStatus.PRODUCTION_CLOSED
        ])
    ).all()

@router.post("/{menu_id}/start")
def start_production(
    menu_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("production"))
):
    """✅ Démarrer manuellement une production (si seuil non atteint mais admin force)"""
    success = ProductionOrchestrator.launch_cooking(db, menu_id)
    if not success:
        raise HTTPException(status_code=400, detail="Impossible de démarrer cette production")
    return {"status": "success", "message": "Production démarrée"}

@router.post("/{menu_id}/ready")
def mark_production_ready(
    menu_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("production"))
):
    """✅ Marquer une production comme prête pour livraison"""
    success = ProductionOrchestrator.finish_cooking(db, menu_id)
    if not success:
        raise HTTPException(status_code=400, detail="Production introuvable ou statut invalide")
    return {"status": "success", "message": "Production marquée comme prête"}

@router.post("/{menu_id}/cancel")
def cancel_production(
    menu_id: str,
    action: ProductionAction,  # { "reason": "string" }
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("production"))
):
    """✅ Annuler une production avec notification clients"""
    success = ProductionOrchestrator.cancel_production(db, menu_id, action.reason)
    if not success:
        raise HTTPException(status_code=400, detail="Impossible d'annuler cette production")
    return {"status": "success", "message": "Production annulée, clients notifiés"}