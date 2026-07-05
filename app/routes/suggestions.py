# app/routes/suggestions.py
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.suggestion import Suggestion
from app.entities.collective_pot import CollectivePot
from app.entities.product import Product
from app.enums import CollectivePotStatus
from app.schemas.suggestion import (
    SuggestionResponse,
    SuggestionCreate,
    LaunchMarmiteRequest,
)
from app.auth import check_permission

logger = logging.getLogger("kemtchop.suggestions")

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])


# ============================================================
# 📱 ENDPOINTS PUBLICS
# ============================================================

@router.get("/", response_model=List[SuggestionResponse])
def get_active_suggestions(db: Session = Depends(get_db)):
    """✅ Récupère toutes les suggestions actives (plats disponibles non financés)"""
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
def launch_marmite(
    suggestion_id: UUID,
    data: LaunchMarmiteRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """
    🚀 TRANSFORMATION MAGIQUE : Suggestion → CollectivePot

    C'est LE endpoint qui fait basculer un plat du statut
    "visible" vers "en financement collectif".

    Le lien se fait UNIQUEMENT via CollectivePot.suggestion_id (unidirectionnel).
    """
    suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not suggestion or not suggestion.is_active:
        raise HTTPException(status_code=404, detail="Suggestion non trouvée ou inactive")

    product = db.query(Product).filter(Product.id == suggestion.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit associé non trouvé")

    # Calculer les prix dérivés
    live_price = round(data.preorder_price * (1 - data.discount_percentage / 100), 2)
    sponsor_pack_price = round(data.preorder_price * data.minimum_orders, 2)

    # ✅ Créer le CollectivePot (le lien suggestion se fait ICI via suggestion_id)
    collective_pot = CollectivePot(
        product_id=suggestion.product_id,
        suggestion_id=suggestion.id,  # ← Lien unidirectionnel CP → Suggestion
        target_date=data.target_date,
        minimum_orders=data.minimum_orders,
        max_orders=data.max_orders,
        preorder_price=data.preorder_price,
        live_price=live_price,
        sponsor_pack_price=sponsor_pack_price,
        discount_percentage=data.discount_percentage,
        bonus_description=data.bonus_description,
        status=CollectivePotStatus.ACTIVE.value,
    )
    db.add(collective_pot)

    # ✅ Désactiver la suggestion (elle est maintenant une marmite)
    suggestion.is_active = False
    # ❌ SUPPRIMÉ : suggestion.collective_pot_id = collective_pot.id
    # Cette colonne n'existe plus. Le lien est uniquement dans CollectivePot.suggestion_id

    db.commit()
    db.refresh(collective_pot)

    logger.info(
        f"🚀 Marmite lancée : {product.name} pour le {data.target_date} "
        f"(objectif {data.minimum_orders} portions)"
    )

    return {
        "status": "success",
        "collective_pot_id": str(collective_pot.id),
        "message": f"Marmite '{product.name}' lancée pour le {data.target_date}",
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