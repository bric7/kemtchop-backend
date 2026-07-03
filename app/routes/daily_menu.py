# app/routes/daily_menu.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import date, datetime, timedelta
from typing import List, Optional

from app.database import get_db
from app.entities.daily_menu import DailyMenu
from app.entities.product import Product
from app.auth import check_permission
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.entities.daily_menu import DailyMenu  # ← Vérifie que ce chemin est correct

from app.schemas.daily_menu import DailyMenuCreate, DailyMenuResponse
router = APIRouter(prefix="/daily-menu", tags=["DailyMenu"])

# ============================================================
# 📅 CONSULTATION (Public)
# ============================================================
@router.get("/tomorrow", response_model=List[DailyMenuResponse])
def get_tomorrow_menus(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None)
):
    """✅ Menus programmés pour demain (public)"""
    tomorrow = date.today() + timedelta(days=1)
    
    query = db.query(DailyMenu).join(Product).filter(
        DailyMenu.occurrence_date == tomorrow,
        DailyMenu.status != "SCHEDULED"  # Exclure les non-ouverts
    )
    
    if category and category != "Tout":
        query = query.filter(Product.category == category)
    
    return query.order_by(DailyMenu.reserved_portions.desc()).all()

@router.get("/today", response_model=List[DailyMenuResponse])
def get_today_menus(db: Session = Depends(get_db)):
    """✅ Menus en cours aujourd'hui (pour suivi)"""
    today = date.today()
    return db.query(DailyMenu).filter(
        DailyMenu.occurrence_date == today,
        DailyMenu.status.in_(["PRODUCTION_CONFIRMED", "PRODUCTION_CLOSED"])
    ).all()

@router.get("/{menu_id}", response_model=DailyMenuResponse)
def get_menu_detail(menu_id: str, db: Session = Depends(get_db)):
    """✅ Détail d'un menu spécifique"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    return menu

# ============================================================
# ⚙️ ADMIN : GESTION DE LA PRODUCTION
# ============================================================
@router.post("/", status_code=201)
def schedule_production(
    data: DailyMenuCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Programmer un produit pour une date donnée"""
    # Vérifier qu'il n'existe pas déjà
    existing = db.query(DailyMenu).filter(
        DailyMenu.product_id == data.product_id,
        DailyMenu.occurrence_date == data.occurrence_date
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce produit est déjà programmé pour cette date")
    
    # Créer le DailyMenu
    new_menu = DailyMenu(
        product_id=data.product_id,
        occurrence_date=data.occurrence_date,
        cutoff_time=data.cutoff_time or "22:00:00",
        status="PREORDER_OPEN",  # Commence en attente du pack
        minimum_production=data.minimum_production or 3,
        max_production=data.max_production,
        pack_price=data.pack_price,
        individual_price=data.individual_price,
        bonus_description=data.bonus_description,
        notes=data.notes
    )
    
    db.add(new_menu)
    db.commit()
    db.refresh(new_menu)
    
    return {"status": "success", "menu_id": new_menu.id, "message": f"{new_menu.product.name} programmé pour {new_menu.occurrence_date}"}

@router.patch("/{menu_id}/status")
def update_menu_status(
    menu_id: str,
    new_status: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Transition d'état contrôlée (ex: PREORDER_OPEN → PRODUCTION_CONFIRMED)"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    
    # Valider la transition
    if not menu.can_transition_to(new_status):
        raise HTTPException(
            status_code=400, 
            detail=f"Transition invalide : {menu.status} → {new_status}"
        )
    
    # Logique métier selon la transition
    if new_status == "PRODUCTION_CONFIRMED" and menu.status == "PREORDER_OPEN":
        # Vérifier le seuil
        if menu.reserved_portions < menu.minimum_production:
            raise HTTPException(
                status_code=400,
                detail=f"Seuil non atteint : {menu.reserved_portions}/{menu.minimum_production} portions"
            )
        menu.launched_at = datetime.utcnow()
    
    old_status = menu.status
    menu.status = new_status
    db.commit()
    
    return {
        "status": "success",
        "menu_id": menu_id,
        "old_status": old_status,
        "new_status": new_status,
        "message": f"{menu.product.name} : {old_status} → {new_status}"
    }

@router.patch("/{menu_id}/capacity")
def update_menu_capacity(
    menu_id: str,
    reserved_portions: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Mise à jour manuelle des portions réservées (sync avec commandes)"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    
    if reserved_portions < 0:
        raise HTTPException(status_code=400, detail="Nombre de portions invalide")
    
    # Auto-close si capacité atteinte
    if menu.max_production and reserved_portions >= menu.max_production:
        if menu.status == "PREORDER_OPEN":
            menu.status = "PRODUCTION_CLOSED"
    
    menu.reserved_portions = reserved_portions
    menu.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "reserved_portions": menu.reserved_portions}

@router.delete("/{menu_id}")
def cancel_production(
    menu_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Annuler une production programmée (seulement si pas de commandes)"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    
    if menu.reserved_portions > 0:
        raise HTTPException(
            status_code=400,
            detail="Impossible d'annuler : des commandes existent déjà"
        )
    
    db.delete(menu)
    db.commit()
    
    return {"status": "success", "message": "Production annulée"}
