# app/routes/production_sessions.py
# ============================================================
# 🏭 KEMTCHOP - Orchestration des Sessions de Production
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import date as datetime_date

from app.database import get_db
from app.entities.product import Product  # Utilisé comme "Recette R&D"
from app.entities.daily_menu import DailyMenu  # Devient notre "Session de Production"
from app.auth import check_permission

router = APIRouter(
    prefix="/production-sessions",
    tags=["Orchestration & Production"]
)

# 📊 1. LE RADAR DE PRODUCTION (Pour ton nouveau Dashboard "Marmites")
@router.get("/active", status_code=status.HTTP_200_OK)
def get_active_production_marmites(db: Session = Depends(get_db)):
    """
    🔥 Lit l'état en temps réel des marmites actives pour le Dashboard.
    Anciennement : "get_current_menu"
    """
    # On récupère les sessions du jour qui sont en phase de vote, cuisson ou livraison
    active_sessions = db.query(DailyMenu).filter(
        DailyMenu.date == datetime_date.today()
    ).all()
    
    marmites = []
    for session in active_sessions:
        # On récupère les détails de la recette associés via Product
        recipe = db.query(Product).filter(Product.id == session.product_id).first()
        
        marmites.append({
            "session_id": session.id,
            "recipe_name": recipe.product_name if recipe else "Recette Inconnue",
            "hub": getattr(session, "hub", "Yaoundé - Principal"), # Évolutif
            "status": session.status, # 'en_attente' (Votes), 'cuisine' (Cuisson), 'livraison', 'termine'
            "metrics": {
                "current_reserved": session.current_reserved, # Tes votes / réservations
                "min_threshold": session.min_threshold,       # Ton seuil critique de marmite
                "max_capacity": session.max_capacity,         # Ta capacité limite de marmite
            },
            "timeline": {
                "delivery_time": session.delivery_time
            }
        })
    return marmites

# 📆 2. CRÉATION D'UNE SESSION DE PRODUCTION (Planification)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_production_session(
    session_data: dict, 
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("plan_production"))
):
    """
    🎯 Crée une Session de Production (Anciennement : Publier un menu)
    Payload attendu : { recipe_id, date, price, min_threshold, max_capacity, delivery_time, is_hero }
    """
    # Vérification que la recette (Product) existe dans le catalogue R&D
    recipe = db.query(Product).filter(Product.id == session_data.get("recipe_id")).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recette R&D introuvable.")

    # Création de la session en réutilisant la table DailyMenu de façon détournée mais ultra-propre
    new_session = DailyMenu(
        product_id=recipe.id,
        date=session_data.get("date", datetime_date.today()),
        price=session_data.get("price", recipe.price),
        min_threshold=session_data.get("min_threshold", 10), # Seuil marmite
        max_capacity=session_data.get("max_capacity", 100),  # Capacité marmite
        delivery_time=session_data.get("delivery_time", "12h00"),
        is_hero=session_data.get("is_hero", False),
        status="en_attente", # Le lot commence toujours en phase de "Vote / Réservation"
        current_reserved=0
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {"status": "session_created", "session_id": new_session.id}