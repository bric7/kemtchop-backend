# app/routes/daily_offers.py
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.entities.daily_offer import DailyOffer
from app.entities.product import Product
from app.enums import ProductionStatus
from app.auth import check_permission
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("kemtchop.daily_offers")
router = APIRouter(prefix="/offers", tags=["Daily Offers"])

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
class ProductSummary(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    image_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class DailyOfferResponse(BaseModel):
    id: str
    product: Optional[ProductSummary] = None
    target_date: date
    status: str
    minimum_threshold: int
    max_capacity: int
    reserved_portions: int
    current_revenue: float
    price_per_unit: float
    progress_percentage: float
    remaining_to_trigger: int
    remaining_capacity: int
    is_threshold_reached: bool
    bonus_description: Optional[str] = None
    triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DailyOfferCreate(BaseModel):
    product_id: int
    target_date: date
    minimum_threshold: int = 4
    max_capacity: int = 20
    price_per_unit: float
    status: Optional[str] = ProductionStatus.PROPOSED.value
    bonus_description: Optional[str] = None
    admin_notes: Optional[str] = None


# ============================================================
# 🔧 HELPER DE SÉRIALISATION SÉCURISÉ
# ============================================================
def _to_offer_response(offer: DailyOffer) -> DailyOfferResponse:
    product_info = None
    if offer.product:
        product_info = ProductSummary(
            id=offer.product.id,
            name=offer.product.name,
            category=offer.product.category,
            image_url=offer.product.image_url,
        )
    
    return DailyOfferResponse(
        id=str(offer.id),
        product=product_info,
        target_date=offer.target_date,
        status=offer.status,
        minimum_threshold=offer.minimum_threshold,
        max_capacity=offer.max_capacity,
        reserved_portions=offer.reserved_portions,
        current_revenue=float(offer.current_revenue or 0.0),
        price_per_unit=float(offer.price_per_unit or 0.0),
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
# 📱 ENDPOINTS PUBLICS
# ============================================================
@router.get("/upcoming", response_model=List[DailyOfferResponse])
def get_upcoming_offers(
    days: int = Query(7, description="Nombre de jours à afficher"),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    db: Session = Depends(get_db)
):
    today = date.today()
    end_date = today + timedelta(days=days)
    
    query = (
        db.query(DailyOffer)
        .options(joinedload(DailyOffer.product))
        .filter(DailyOffer.target_date >= today)
        .filter(DailyOffer.target_date <= end_date)
        .filter(DailyOffer.status != ProductionStatus.CANCELLED.value)
        .order_by(DailyOffer.target_date.asc())
    )
    
    if category and category != "Tout":
        query = query.join(Product).filter(Product.category == category)
    
    try:
        offers = query.all()
        # Tri secondaire en Python pour le pourcentage
        offers.sort(key=lambda o: (o.target_date, -o.progress_percentage))
        result = [_to_offer_response(o) for o in offers]
        logger.info(f"📊 {len(result)} offres culinaires à venir (sur {days} jours)")
        return result
    except Exception as e:
        logger.error(f"❌ Erreur récupération offres à venir : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")


@router.get("/tomorrow", response_model=List[DailyOfferResponse])
def get_tomorrow_offers(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
):
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


# ============================================================
# 👑 ENDPOINTS ADMIN
# ============================================================

# ✅ NOUVEAU : Endpoint manquant pour la création manuelle d'une offre
@router.post("/", status_code=201, response_model=DailyOfferResponse)
def create_daily_offer(
    payload: DailyOfferCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Créer une nouvelle offre quotidienne manuellement (ex: pour le Menu du Jour en urgence)"""
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    existing = db.query(DailyOffer).filter(
        DailyOffer.product_id == payload.product_id,
        DailyOffer.target_date == payload.target_date
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une offre existe déjà pour ce produit à cette date")
    
    from app.routes.settings import get_or_create_settings
    from app.utils.timezone import get_business_date, combine_business_datetime
    
    settings = get_or_create_settings(db)
    business_today = get_business_date()
    
    # Calcul des cutoffs basés sur les settings
    reservation_cutoff_at = combine_business_datetime(payload.target_date - timedelta(days=1), settings.reservation_cutoff_time)
    order_cutoff_at = combine_business_datetime(payload.target_date, settings.order_cutoff_time)
    
    new_offer = DailyOffer(
        product_id=payload.product_id,
        target_date=payload.target_date,
        minimum_threshold=payload.minimum_threshold,
        max_capacity=payload.max_capacity or 20,
        price_per_unit=payload.price_per_unit,
        status=payload.status or ProductionStatus.PROPOSED.value,
        bonus_description=payload.bonus_description,
        reserved_portions=0,
        reservation_cutoff_at=reservation_cutoff_at,
        order_cutoff_at=order_cutoff_at,
    )
    
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)
    
    logger.info(f"✅ Offre créée manuellement par admin : {product.name} pour le {payload.target_date}")
    return _to_offer_response(new_offer)


@router.post("/auto-generate")
def auto_generate_offers(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
    days: int = Query(7, description="Nombre de jours à générer"),
):
    """Génère automatiquement les offres et les reels pour les X prochains jours."""
    import random
    from app.entities.reel import Reel
    
    today = date.today()
    created_offers = []
    
    hero_products = db.query(Product).filter(Product.is_hero == True).all()
    if not hero_products:
        raise HTTPException(status_code=400, detail="Aucun produit 'hero' trouvé.")
    
    for day_offset in range(1, days + 1):
        target_date = today + timedelta(days=day_offset)
        selected_products = random.sample(hero_products, min(len(hero_products), random.randint(2, 3)))
        
        for product in selected_products:
            existing = db.query(DailyOffer).filter(
                DailyOffer.product_id == product.id,
                DailyOffer.target_date == target_date,
            ).first()
            
            if existing:
                continue
            
            new_offer = DailyOffer(
                product_id=product.id,
                target_date=target_date,
                minimum_threshold=4,
                max_capacity=20,
                price_per_unit=product.price or 2500,
                status=ProductionStatus.PROPOSED.value,
            )
            db.add(new_offer)
            db.flush()
            
            video_url = getattr(product, 'video_url', None)
            image_url = product.image_url or "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=600&auto=format&fit=crop"
            
            new_reel = Reel(
                title=f"Découvrez notre {product.name} ! 🔥",
                daily_offer_id=new_offer.id,
                video_url=video_url,
                image_url=image_url,
                is_active=True,
                priority=random.randint(1, 10),
            )
            db.add(new_reel)
            
            created_offers.append({"product": product.name, "date": str(target_date)})
    
    db.commit()
    logger.info(f"🎯 Auto-génération : {len(created_offers)} offres créées")
    return {"status": "success", "count": len(created_offers)}