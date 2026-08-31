# app/routes/daily_offers.py
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import check_permission
from app.database import get_db
from app.entities.daily_offer import DailyOffer
from app.entities.product import Product
from app.enums import ProductionStatus
from app.schemas.daily_offer import DailyOfferCreate, DailyOfferResponse, ProductSummary

logger = logging.getLogger("kemtchop.daily_offers")
router = APIRouter(prefix="/offers", tags=["Daily Offers"])


def _to_offer_response(offer: DailyOffer) -> DailyOfferResponse:
    """Helper interne pour sérialiser une DailyOffer en DailyOfferResponse."""
    return DailyOfferResponse(
        id=offer.id,
        product=ProductSummary(
            id=offer.product.id,
            name=offer.product.name,
            category=offer.product.category,
            image_url=offer.product.image_url,
        ),
        target_date=offer.target_date,
        status=offer.status,
        minimum_threshold=offer.minimum_threshold,
        max_capacity=offer.max_capacity,
        reserved_portions=offer.reserved_portions,
        current_revenue=float(offer.current_revenue),
        price_per_unit=float(offer.price_per_unit),
        progress_percentage=float(offer.progress_percentage),
        remaining_to_trigger=int(offer.remaining_to_trigger),
        remaining_capacity=int(offer.remaining_capacity),
        is_threshold_reached=offer.is_threshold_reached,
        bonus_description=offer.bonus_description,
        triggered_at=offer.triggered_at,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
    )


# ============================================================
# 📱 ENDPOINTS PUBLICS (Mobile Application)
# ============================================================

@router.get("/upcoming", response_model=List[DailyOfferResponse])
def get_upcoming_offers(
    days: int = Query(7, description="Nombre de jours à afficher (défaut: 7)"),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    db: Session = Depends(get_db)
):
    """✅ Récupère les offres des X prochains jours pour permettre la précommande future."""
    today = date.today()
    end_date = today + timedelta(days=days)
    
    query = (
        db.query(DailyOffer)
        .options(joinedload(DailyOffer.product))
        .filter(DailyOffer.target_date >= today)
        .filter(DailyOffer.target_date <= end_date)
        .filter(DailyOffer.status != ProductionStatus.CANCELLED.value)
        .order_by(DailyOffer.target_date.asc(), DailyOffer.progress_percentage.desc())
    )
    
    if category and category != "Tout":
        query = query.join(Product).filter(Product.category == category)
    
    offers = query.all()
    result = [_to_offer_response(o) for o in offers]
    
    logger.info(f"📊 {len(result)} offres culinaires à venir (sur {days} jours)")
    return result


@router.get("/tomorrow", response_model=List[DailyOfferResponse])
def get_tomorrow_offers(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
):
    """Récupère les offres culinaires prévues pour demain (legacy)."""
    tomorrow = date.today() + timedelta(days=1)

    query = (
        db.query(DailyOffer)
        .options(joinedload(DailyOffer.product))
        .filter(DailyOffer.target_date == tomorrow)
        .filter(DailyOffer.status != ProductionStatus.CANCELLED.value)
    )

    if category and category != "Tout":
        query = query.join(Product).filter(Product.category == category)

    offers = query.all()
    result = [_to_offer_response(o) for o in offers]
    result.sort(key=lambda x: x.progress_percentage, reverse=True)

    logger.info(f"📊 {len(result)} offres culinaires pour demain")
    return result


@router.get("/today", response_model=List[DailyOfferResponse])
def get_today_offers(db: Session = Depends(get_db)):
    """Récupère les offres culinaires du jour."""
    today = date.today()
    offers = (
        db.query(DailyOffer)
        .options(joinedload(DailyOffer.product))
        .filter(
            DailyOffer.target_date == today,
            DailyOffer.status.in_([
                ProductionStatus.PROPOSED.value,
                ProductionStatus.CONFIRMED.value,
                ProductionStatus.COOKING.value,
            ]),
        )
        .all()
    )
    return [_to_offer_response(o) for o in offers]


@router.get("/{offer_id}", response_model=DailyOfferResponse)
def get_offer_detail(offer_id: UUID, db: Session = Depends(get_db)):
    """Détail d'une offre spécifique."""
    offer = (
        db.query(DailyOffer)
        .options(joinedload(DailyOffer.product))
        .filter(DailyOffer.id == offer_id)
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    return _to_offer_response(offer)


# ============================================================
# ⚙️ ENDPOINTS ADMIN
# ============================================================

@router.post("/", status_code=201)
def create_daily_offer(
    data: DailyOfferCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """Admin : Lancer une nouvelle proposition de plat pour une date donnée."""
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    existing = (
        db.query(DailyOffer)
        .filter(
            DailyOffer.product_id == data.product_id,
            DailyOffer.target_date == data.target_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Une offre existe déjà pour {product.name} le {data.target_date}",
        )

    today = date.today()
    initial_status = data.status or ProductionStatus.PROPOSED.value

    if data.target_date < today:
        raise HTTPException(status_code=400, detail="Date passée interdite")

    if data.target_date == today and initial_status == ProductionStatus.PROPOSED.value:
        raise HTTPException(
            status_code=400,
            detail="Pour aujourd'hui, passez directement au statut 'confirmed'"
        )

    new_offer = DailyOffer(
        product_id=data.product_id,
        target_date=data.target_date,
        minimum_threshold=data.minimum_threshold,
        max_capacity=data.max_capacity,
        price_per_unit=data.price_per_unit,
        status=initial_status,
        bonus_description=data.bonus_description,
        admin_notes=data.admin_notes,
        triggered_at=datetime.utcnow() if initial_status == ProductionStatus.CONFIRMED.value else None,
        triggered_by_admin=(initial_status == ProductionStatus.CONFIRMED.value),
        admin_override_reason="Lancement direct en Menu du Jour" if initial_status == ProductionStatus.CONFIRMED.value else None,
    )
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)

    logger.info(f"🎯 Offre créée : {product.name} pour le {data.target_date}")
    return {
        "status": "success",
        "offer_id": str(new_offer.id),
        "message": f"Offre '{product.name}' créée pour le {data.target_date}",
    }


@router.patch("/{offer_id}/status")
async def update_offer_status(
    offer_id: UUID,
    new_status: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """Admin : Forcer manuellement le changement de statut d'une production."""
    offer = db.query(DailyOffer).filter(DailyOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    try:
        new_status_enum = ProductionStatus(new_status)
    except ValueError:
        valid_values = [s.value for s in ProductionStatus]
        raise HTTPException(status_code=400, detail=f"Statut invalide. Valeurs : {valid_values}")

    if not offer.can_transition_to(new_status_enum):
        raise HTTPException(
            status_code=400,
            detail=f"Transition invalide : {offer.status} → {new_status}",
        )

    old_status = offer.status
    offer.status = new_status_enum.value
    offer.updated_at = datetime.utcnow()

    # ✅ TRAÇABILITÉ : Si l'admin force le passage en CONFIRMED avant le seuil
    if new_status_enum == ProductionStatus.CONFIRMED and not offer.is_threshold_reached:
        offer.triggered_by_admin = True
        offer.admin_override_reason = "Lancement manuel par l'admin avant seuil"
        offer.triggered_at = datetime.utcnow()
        logger.warning(f"⚠️ LANCEMENT FORCÉ par l'admin pour {offer.product.name}")
    elif new_status_enum == ProductionStatus.CONFIRMED:
        offer.triggered_at = datetime.utcnow()

    # 🔗 SYNCHRONISATION AVEC LES COMMANDES CLIENTS
    from app.entities.order import Order
    from app.enums import OrderStatus
    
    if new_status_enum.value == "cooking":
        db.query(Order).filter(
            Order.daily_offer_id == offer_id,
            Order.status == OrderStatus.PAID.value
        ).update({"status": OrderStatus.PREPARING.value})

    elif new_status_enum.value in ["ready", "delivered"]:
        db.query(Order).filter(
            Order.daily_offer_id == offer_id,
            Order.status.in_([OrderStatus.PAID.value, OrderStatus.PREPARING.value])
        ).update({"status": OrderStatus.READY_TO_SHIP.value})

    db.commit()

    logger.info(f"🔄 Production {offer.product.name} : {old_status} → {new_status}")
    
    return {
        "status": "success",
        "offer_id": str(offer_id),
        "old_status": old_status,
        "new_status": new_status,
    }