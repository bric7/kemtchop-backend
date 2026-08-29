# app/routes/suggestions.py
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.suggestion import Suggestion
from app.entities.daily_offer import DailyOffer
from app.entities.product import Product
from app.enums import ProductionStatus
from app.schemas.suggestion import (
    SuggestionResponse,
    SuggestionCreate,
    LaunchOfferRequest,
)
from app.auth import check_permission

logger = logging.getLogger("kemtchop.suggestions")

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])


# ============================================================
# 📱 ENDPOINTS PUBLICS
# ============================================================

@router.get("/", response_model=List[SuggestionResponse])
def get_active_suggestions(db: Session = Depends(get_db)):
    """✅ Récupère toutes les suggestions actives (plats du catalogue proposés)"""
    suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.is_active == True)
        .order_by(Suggestion.created_at.desc())
        .all()
    )
    return suggestions


@router.post("/{suggestion_id}/interest")
def add_interest(suggestion_id: UUID, db: Session = Depends(get_db)):
    """✅ Voter pour une suggestion (incrémenter interest_count)"""
    suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not suggestion or not suggestion.is_active:
        raise HTTPException(status_code=404, detail="Suggestion non trouvée ou inactive")

    suggestion.interest_count += 1
    db.commit()

    return {"status": "success", "interest_count": suggestion.interest_count}


# ============================================================
# ⚙️ ENDPOINTS ADMIN
# ============================================================

@router.post("/", status_code=201, response_model=SuggestionResponse)
def create_suggestion(
    data: SuggestionCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """✅ Créer une nouvelle suggestion (admin)"""
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    # Vérifier qu'il n'y a pas déjà une suggestion active pour ce produit
    existing = (
        db.query(Suggestion)
        .filter(Suggestion.product_id == data.product_id, Suggestion.is_active == True)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Une suggestion active existe déjà pour ce produit")

    new_suggestion = Suggestion(
        product_id=data.product_id,
        suggested_date=data.suggested_date,
        notes=data.notes,
    )
    db.add(new_suggestion)
    db.commit()
    db.refresh(new_suggestion)

    logger.info(f"💡 Suggestion créée pour {product.name}")
    return new_suggestion


@router.post("/{suggestion_id}/launch", status_code=201)
def launch_daily_offer(
    suggestion_id: UUID,
    data: LaunchOfferRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """
    🚀 TRANSFORMATION : Suggestion → DailyOffer
    Définit une date et un seuil pour transformer une suggestion en offre active.
    """
    suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not suggestion or not suggestion.is_active:
        raise HTTPException(status_code=404, detail="Suggestion non trouvée ou inactive")

    product = db.query(Product).filter(Product.id == suggestion.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit associé non trouvé")

    # Créer la DailyOffer
    new_offer = DailyOffer(
        product_id=suggestion.product_id,
        suggestion_id=suggestion.id,
        target_date=data.target_date,
        minimum_threshold=data.minimum_threshold,
        max_capacity=data.max_capacity,
        price_per_unit=data.price_per_unit,
        bonus_description=data.bonus_description,
        status=ProductionStatus.PROPOSED.value,
    )
    db.add(new_offer)

    # Désactiver la suggestion
    suggestion.is_active = False

    db.commit()
    db.refresh(new_offer)

    logger.info(
        f"🚀 Offre lancée : {product.name} pour le {data.target_date} "
        f"(seuil {data.minimum_threshold} portions)"
    )

    return {
        "status": "success",
        "offer_id": str(new_offer.id),
        "message": f"Offre '{product.name}' lancée pour le {data.target_date}",
    }


@router.delete("/{suggestion_id}")
def delete_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """✅ Supprimer une suggestion (admin)"""
    suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion non trouvée")

    suggestion.is_active = False
    db.commit()

    logger.info(f"🗑️ Suggestion désactivée : {suggestion_id}")
    return {"status": "success", "message": "Suggestion désactivée"}
