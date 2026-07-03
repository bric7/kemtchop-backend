# app/routes/daily_menu.py
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.daily_menu import DailyMenu
from app.entities.product import Product
from app.enums import ProductionStatus  # ✅ NOUVEL IMPORT
from app.auth import check_permission
from app.schemas.daily_menu import DailyMenuCreate, DailyMenuResponse

logger = logging.getLogger("kemtchop.daily_menu")

router = APIRouter(prefix="/daily-menu", tags=["DailyMenu"])

# ============================================================
# 📅 CONSULTATION (Flux Mobile)
# ============================================================

@router.get("/tomorrow", response_model=List[DailyMenuResponse])
def get_tomorrow_menus(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None)
):
    """✅ Menus planifiés pour demain (ouverts aux réservations)"""
    tomorrow = date.today() + timedelta(days=1)
    
    # ✅ Utiliser les valeurs d'enum pour le filtre
    query = db.query(DailyMenu).join(Product).filter(
        DailyMenu.occurrence_date == tomorrow,
        DailyMenu.status.in_([
            ProductionStatus.PUBLISHED.value, 
            ProductionStatus.CONFIRMED.value
        ])
    )
    
    if category and category != "Tout":
        query = query.filter(Product.category == category)
        
    return query.order_by(DailyMenu.reserved_portions.desc()).all()


@router.get("/today", response_model=List[DailyMenuResponse])
def get_today_menus(db: Session = Depends(get_db)):
    """✅ Productions en cours aujourd'hui (suivi cuisine)"""
    today = date.today()
    
    # ✅ Filtrer avec les enums
    return db.query(DailyMenu).filter(
        DailyMenu.occurrence_date == today,
        DailyMenu.status.in_([
            ProductionStatus.CONFIRMED.value,
            ProductionStatus.COOKING.value, 
            ProductionStatus.READY.value,
            ProductionStatus.DELIVERED.value
        ])
    ).all()


@router.get("/{menu_id}", response_model=DailyMenuResponse)
def get_menu_detail(menu_id: str, db: Session = Depends(get_db)):
    """✅ Détail d'un menu spécifique"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    return menu


# ============================================================
# ⚙️ ADMIN : Gestion de la production
# ============================================================

@router.post("/", status_code=201)
def schedule_production(
    data: DailyMenuCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Programmer un produit pour une date donnée"""
    existing = db.query(DailyMenu).filter(
        DailyMenu.product_id == data.product_id,
        DailyMenu.occurrence_date == data.occurrence_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Ce produit est déjà programmé pour cette date"
        )
    
    # ✅ Initialiser avec la valeur d'enum
    new_menu = DailyMenu(
        product_id=data.product_id,
        occurrence_date=data.occurrence_date,
        cutoff_time=data.cutoff_time or "18:00:00",
        status=ProductionStatus.PUBLISHED.value,  # ✅ Commence en "published"
        minimum_production=data.minimum_production or 3,
        max_production=data.max_production or 25,
        reserved_portions=0,
        pack_price=data.pack_price,
        individual_price=data.individual_price,
        bonus_description=data.bonus_description,
        notes=data.notes
    )
    
    db.add(new_menu)
    db.commit()
    db.refresh(new_menu)
    
    return {
        "status": "success", 
        "menu_id": str(new_menu.id), 
        "message": f"{new_menu.product.name} programmé pour {new_menu.occurrence_date}"
    }


@router.patch("/{menu_id}/status")
def update_menu_status(
    menu_id: str,
    new_status: str,  # Reçu depuis l'API comme string
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Transition d'état contrôlée via enum"""
    menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    
    # ✅ Convertir la string reçue en Enum pour validation
    try:
        new_status_enum = ProductionStatus(new_status)
    except ValueError:
        valid_values = [s.value for s in ProductionStatus]
        raise HTTPException(
            status_code=400, 
            detail=f"Statut invalide. Valeurs acceptées : {valid_values}"
        )
    
    # ✅ Valider la transition via la méthode type-safe
    if not menu.can_transition_to(new_status_enum):
        raise HTTPException(
            status_code=400, 
            detail=f"Transition invalide : {menu.status} → {new_status}"
        )
    
    # ✅ Logique métier selon la transition
    if new_status_enum == ProductionStatus.CONFIRMED and menu.status_enum == ProductionStatus.PUBLISHED:
        if menu.reserved_portions < menu.minimum_production:
            raise HTTPException(
                status_code=400,
                detail=f"Seuil non atteint : {menu.reserved_portions}/{menu.minimum_production}"
            )
        menu.launched_at = datetime.utcnow()
    
    old_status = menu.status
    menu.status = new_status_enum.value  # ✅ Stocker la valeur string en BDD
    menu.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "success",
        "menu_id": menu_id,
        "old_status": old_status,
        "new_status": new_status,
        "message": f"{menu.product.name} : {old_status} → {new_status}"
    }


@router.delete("/{menu_id}")
def cancel_production(
    menu_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Annuler une production (seulement si pas de commandes)"""
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