# app/routes/daily_menu.py
# ============================================================
# 🍲 KEMTCHOP - Logiciel d'Orchestration des Menus Quotidiens
# ============================================================

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.daily_menu import DailyMenu
from app.entities.product import Product
from app.auth import check_permission
from app.schemas.daily_menu import DailyMenuCreate, DailyMenuResponse

logger = logging.getLogger("kemtchop.daily_menu")

router = APIRouter(prefix="/daily-menu", tags=["DailyMenu"])

# ============================================================
# 📅 CONSULTATION (Flux Applicatif Mobile)
# ============================================================

@router.get("/tomorrow", response_model=List[DailyMenuResponse])
def get_tomorrow_menus(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None)
):
    """✅ Récupère les menus planifiés pour demain (Séparés par l'état mobile)"""
    tomorrow = date.today() + timedelta(days=1)
    
    # On récupère tous les menus ouverts pour demain (qu'ils soient confirmés ou en attente)
    query = db.query(DailyMenu).join(Product).filter(
        DailyMenu.occurrence_date == tomorrow,
        DailyMenu.status.in_(["waiting_first_order", "confirmed"])
    )
    
    if category and category != "Tout":
        query = query.filter(Product.category == category)
        
    # Tri automatique par intérêt décroissant (Dynamique collective de réservation)
    return query.order_by(DailyMenu.reserved_portions.desc()).all()


@router.get("/today", response_model=List[DailyMenuResponse])
def get_today_menus(db: Session = Depends(get_db)):
    """✅ Récupère les productions en cours aujourd'hui (Suivi en temps réel)"""
    today = date.today()
    return db.query(DailyMenu).filter(
        DailyMenu.occurrence_date == today,
        DailyMenu.status.in_(["confirmed", "cooking", "completed"])
    ).all()


@router.get("/{menu_id}", response_model=DailyMenuResponse)
def get_menu_detail(menu_id: str, db: Session = Depends(get_db)):
    """✅ Fiche descriptive d'un batch ou d'un menu spécifique"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu non trouvé")
    return menu


# ============================================================
# ⚙️ ADMIN / UNIVERS PLANIFICATION (Tableau de Bord)
# ============================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
def schedule_production(
    data: DailyMenuCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Ajouter un plat dans la compétition de production de demain"""
    # Éviter qu'un plat soit planifié deux fois la même journée
    existing = db.query(DailyMenu).filter(
        DailyMenu.product_id == data.product_id,
        DailyMenu.occurrence_date == data.occurrence_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Ce produit fait déjà partie de la planification pour cette date"
        )
    
    # Initialisation native selon la logique KEMTCHOP
    new_menu = DailyMenu(
        product_id=data.product_id,
        occurrence_date=data.occurrence_date,
        cutoff_time=data.cutoff_time or "18:00:00", # Fermeture stricte à 18h camerounaise
        status="waiting_first_order",                # Commence au statut "À lancer"
        minimum_production=data.minimum_production or 3,
        max_production=data.max_production or 25,
        reserved_portions=0
    )
    
    db.add(new_menu)
    db.commit()
    db.refresh(new_menu)
    
    return {
        "status": "success", 
        "menu_id": new_menu.id, 
        "message": f"{new_menu.product.product_name} injecté en état 'À lancer' pour le {new_menu.occurrence_date}"
    }


@router.patch("/{menu_id}/status")
def update_menu_status(
    menu_id: str,
    new_status: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Force la transition d'état d'une ligne culinaire depuis le Dashboard Admin"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu non trouvé")
    
    # Validation du cycle de vie (Assure-toi que ton entité DailyMenu possède cette méthode)
    if hasattr(menu, 'can_transition_to') and not menu.can_transition_to(new_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Mouvement interdit : {menu.status} → {new_status}"
        )
    
    old_status = menu.status
    menu.status = new_status
    menu.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "success",
        "menu_id": menu_id,
        "old_status": old_status,
        "new_status": new_status,
        "message": f"Statut de production mis à jour : {new_status}"
    }


@router.delete("/{menu_id}")
def cancel_production(
    menu_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Retirer un plat de la programmation (Seulement si vierge de tout engagement client)"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu non trouvé")
    
    if menu.reserved_portions > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interdiction : Cette ligne a déjà engagé des fonds clients. Procéder à une annulation avec remboursement."
        )
    
    db.delete(menu)
    db.commit()
    
    return {"status": "success", "message": "Plat retiré du planning de production."}