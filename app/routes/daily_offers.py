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
from app.entities.order import Order
from app.enums import ProductionStatus, OrderStatus
from app.schemas.daily_offer import DailyOfferCreate, DailyOfferResponse, ProductSummary
from app.services.notification_service import NotificationService

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

@router.get("/tomorrow", response_model=List[DailyOfferResponse])
def get_tomorrow_offers(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
):
    """Récupère les offres culinaires prévues pour demain."""
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

    # Trier par progression vers le déclenchement
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
# ⚙️ ENDPOINTS ADMIN (Gestion du catalogue du jour)
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
        raise HTTPException(status_code=404, detail="Produit non trouvé dans le catalogue")

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

    # ⚖️ APPLICATION DE LA LOI J+1
    today = date.today()
    initial_status = data.status or ProductionStatus.PROPOSED.value

    if data.target_date < today:
        raise HTTPException(
            status_code=400,
            detail="La date de l'offre ne peut pas être dans le passé."
        )

    if data.target_date == today and initial_status == ProductionStatus.PROPOSED.value:
        raise HTTPException(
            status_code=400,
            detail="Les réservations (À réserver) ne sont possibles que pour J+1 minimum. Pour aujourd'hui, passez directement au statut 'confirmed' (Menu du Jour)."
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
        triggered_at=datetime.utcnow() if initial_status == ProductionStatus.CONFIRMED.value else None
    )
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)

    logger.info(
        "🎯 Offre créée : %s pour le %s (seuil déclenchement : %d portions)",
        product.name,
        data.target_date,
        data.minimum_threshold,
    )
    return {
        "status": "success",
        "offer_id": str(new_offer.id),
        "message": f"Offre '{product.name}' proposée pour le {data.target_date}",
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
        raise HTTPException(
            status_code=400,
            detail=f"Statut invalide. Valeurs acceptées : {valid_values}",
        )

    if not offer.can_transition_to(new_status_enum):
        raise HTTPException(
            status_code=400,
            detail=f"Transition invalide : {offer.status} → {new_status}",
        )

    old_status = offer.status
    offer.status = new_status_enum.value
    offer.updated_at = datetime.utcnow()

    if new_status_enum == ProductionStatus.CONFIRMED:
        offer.triggered_at = datetime.utcnow()

    # 🔗 SYNCHRONISATION AVEC LES COMMANDES CLIENTS (Machine d'État KemTchop v3.0)
    if new_status_enum == ProductionStatus.COOKING:
        # Tous les clients payés passent en "Préparation"
        db.query(Order).filter(
            Order.daily_offer_id == offer_id,
            Order.status == OrderStatus.PAID.value
        ).update({"status": OrderStatus.PREPARING.value})

    elif new_status_enum == ProductionStatus.READY:
        # Tous les clients passent en "Prêt à livrer"
        db.query(Order).filter(
            Order.daily_offer_id == offer_id,
            Order.status.in_([OrderStatus.PAID.value, OrderStatus.PREPARING.value])
        ).update({"status": OrderStatus.READY_TO_SHIP.value})

    elif new_status_enum == ProductionStatus.DELIVERING:
        # Cascade vers les commandes individuelles : "En livraison"
        db.query(Order).filter(
            Order.daily_offer_id == offer_id,
            Order.status == OrderStatus.READY_TO_SHIP.value
        ).update({"status": OrderStatus.SHIPPING.value})

    elif new_status_enum == ProductionStatus.DELIVERED:
        # Fermeture de toutes les commandes liées
        db.query(Order).filter(
            Order.daily_offer_id == offer_id,
            Order.status == OrderStatus.SHIPPING.value
        ).update({"status": OrderStatus.DELIVERED.value})

    db.commit()

    # 🔔 Notification de changement de statut (protégée par try/except)
    try:
        await NotificationService.notify_production_status_change(
            str(offer_id),
            offer.product.name if offer.product else "Offre",
            new_status
        )
    except Exception as e:
        logger.warning(f"Échec de la notification de changement de statut : {e}")

    logger.info(
        "🔄 Production %s : %s → %s",
        offer.product.name if offer.product else "?",
        old_status,
        new_status,
    )
    
    return {
        "status": "success",
        "offer_id": str(offer_id),
        "old_status": old_status,
        "new_status": new_status,
    }

@router.post("/auto-generate", status_code=201)
def auto_generate_offers(
    days: int = Query(7, ge=1, le=14),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    """
    🪄 Admin : Génère automatiquement des propositions (PROPOSED)
    pour les produits 'Hero' sur les X prochains jours.
    """
    hero_products = db.query(Product).filter(Product.is_hero == True).all()
    if not hero_products:
        # Fallback si pas de hero : prendre les 5 premiers produits
        hero_products = db.query(Product).limit(5).all()

    created_count = 0
    today = date.today()

    for i in range(1, days + 1):
        target_date = today + timedelta(days=i)
        for product in hero_products:
            # Vérifier si une offre existe déjà
            existing = db.query(DailyOffer).filter(
                DailyOffer.product_id == product.id,
                DailyOffer.target_date == target_date
            ).first()

            if not existing:
                new_offer = DailyOffer(
                    product_id=product.id,
                    target_date=target_date,
                    minimum_threshold=4, # Valeur par défaut KemTchop
                    price_per_unit=product.price_solo or product.price,
                    status=ProductionStatus.PROPOSED.value
                )
                db.add(new_offer)
                created_count += 1

    db.commit()
    return {
        "status": "success",
        "message": f"{created_count} offres générées pour les {days} prochains jours.",
        "products_count": len(hero_products)
    }
