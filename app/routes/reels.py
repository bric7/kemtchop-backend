# app/routes/reels.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import date
import logging
import uuid

from app.database import get_db
from app.entities.reel import Reel
from app.entities.daily_offer import DailyOffer
from app.entities.product import Product
from app.enums import ProductionStatus

logger = logging.getLogger("kemtchop.reels")
router = APIRouter(prefix="/reels", tags=["Reels"])

class ReelProductInfo(BaseModel):
    name: str
    image_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ReelResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    daily_offer_id: Optional[UUID] = None
    product: Optional[ReelProductInfo] = None
    status: Optional[str] = None
    is_threshold_reached: bool = False
    target_date: Optional[date] = None
    price_per_unit: Optional[float] = None
    reserved_portions: int = 0
    minimum_threshold: int = 0
    button_label: str = "VOIR"
    urgency_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

def _map_to_response(reel, offer) -> dict:
    """Helper pour transformer un Reel et son Offre en ReelResponse"""
    # 1. Résolution du produit (Priorité : Offre > Reel)
    product_name = "Plat KemTchop"
    if offer and offer.product:
        product_name = offer.product.name
    elif hasattr(reel, 'product_name') and reel.product_name:
        product_name = reel.product_name

    # 2. Résolution des médias (Priorité : Reel > Offre > Produit)
    video_url = getattr(reel, 'video_url', None)
    image_url = getattr(reel, 'image_url', None)

    if offer:
        if not video_url:
            video_url = offer.video_url
        if not image_url:
            image_url = offer.image_url

        if offer.product:
            if not video_url:
                video_url = offer.product.video_url
            if not image_url:
                image_url = offer.product.image_url

    # 3. Paramètres de vente et statut
    button_label = "COMMANDER"
    urgency_message = "C'est prêt chez KemTchop !"
    is_threshold_reached = True
    status = "confirmed"
    target_date = None
    price_per_unit = getattr(reel, 'price', None)
    reserved_portions = 0
    minimum_threshold = 0

    if offer:
        status = offer.status
        is_threshold_reached = offer.is_threshold_reached
        target_date = offer.target_date
        price_per_unit = offer.price_per_unit
        reserved_portions = offer.reserved_portions
        minimum_threshold = offer.minimum_threshold

        status_lower = status.lower() if status else "proposed"
        if status_lower in ["proposed", "reservation"]:
            button_label = "RÉSERVER"
            remaining = max(0, minimum_threshold - reserved_portions)
            urgency_message = f"🔥 Encore {remaining} portions"
            is_threshold_reached = False
        elif status_lower == "confirmed":
            button_label = "COMMANDER"
            urgency_message = "✅ Production garantie !"
        elif status_lower == "cooking":
            button_label = "👨‍🍳 EN CUISINE"
            urgency_message = "Préparation en cours"
        elif status_lower == "delivering":
            button_label = "🚚 EN ROUTE"
            urgency_message = "En cours de livraison"

    return {
        "id": reel.id if hasattr(reel, 'id') and reel.id else uuid.uuid4(),
        "title": getattr(reel, 'title', None) or product_name,
        "video_url": video_url,
        "image_url": image_url,
        "daily_offer_id": offer.id if offer else None,
        "product": {
            "name": product_name,
            "image_url": image_url
        },
        "status": status,
        "is_threshold_reached": is_threshold_reached,
        "target_date": target_date,
        "price_per_unit": price_per_unit,
        "reserved_portions": reserved_portions,
        "minimum_threshold": minimum_threshold,
        "button_label": button_label,
        "urgency_message": urgency_message
    }

@router.get("/", response_model=List[ReelResponse])
def get_reels(db: Session = Depends(get_db)):
    """
    ✅ Retourne les Reels actifs + Auto-génère des Reels pour les produits/offres avec vidéo.
    """
    try:
        # 1. Récupérer les Reels créés explicitement
        reels = (
            db.query(Reel)
            .options(joinedload(Reel.daily_offer).joinedload(DailyOffer.product))
            .filter(Reel.is_active == True)
            .order_by(Reel.priority.desc(), Reel.created_at.desc())
            .all()
        )

        result = []
        seen_offer_ids = set()

        for reel in reels:
            if reel.daily_offer_id:
                seen_offer_ids.add(str(reel.daily_offer_id))
            result.append(_map_to_response(reel, reel.daily_offer))

        # 2. AUTO-REELS : Offres actives avec vidéo (Produit ou Offre) sans Reel explicite
        auto_offers = (
            db.query(DailyOffer)
            .join(Product)
            .filter((Product.video_url != None) | (DailyOffer.video_url != None))
            .filter(DailyOffer.status.in_(["proposed", "reservation", "confirmed", "cooking"]))
            .filter(~DailyOffer.id.in_(seen_offer_ids))
            .all()
        )

        for offer in auto_offers:
            seen_offer_ids.add(str(offer.id))
            virtual_reel = Reel(
                id=uuid.uuid4(),
                title=offer.product.name,
                video_url=offer.video_url or offer.product.video_url,
                image_url=offer.image_url or offer.product.image_url,
                daily_offer_id=offer.id
            )
            result.append(_map_to_response(virtual_reel, offer))

        # 3. PRODUITS AVEC VIDÉO SANS OFFRES (Nouveaux uploads)
        seen_product_names = {r['product']['name'] for r in result if r.get('product')}

        products_with_video = (
            db.query(Product)
            .filter(Product.video_url != None)
            .all()
        )

        for p in products_with_video:
            if p.name in seen_product_names:
                continue

            virtual_reel = Reel(
                id=uuid.uuid4(),
                title=p.name,
                video_url=p.video_url,
                image_url=p.image_url,
                daily_offer_id=None
            )
            result.append(_map_to_response(virtual_reel, None))

        return result

    except Exception as e:
        logger.error(f"❌ Erreur récupération reels : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne serveur lors de la récupération des reels")
