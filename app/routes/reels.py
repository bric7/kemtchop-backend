# app/routes/reels.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import date
import logging

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
    id: int
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
    button_label = "COMMANDER"
    urgency_message = "C'est prêt chez KemTchop !"
    is_threshold_reached = True
    status = "confirmed"
    target_date = None
    price_per_unit = reel.price if hasattr(reel, 'price') else None
    reserved_portions = 0
    minimum_threshold = 0

    # Fallback product info depuis le Reel (Legacy Admin)
    product_info = {
        "name": reel.product_name if hasattr(reel, 'product_name') and reel.product_name else "Plat KemTchop",
        "image_url": reel.image_url
    }

    if offer:
        status = offer.status
        is_threshold_reached = offer.is_threshold_reached
        target_date = offer.target_date
        price_per_unit = offer.price_per_unit
        reserved_portions = offer.reserved_portions
        minimum_threshold = offer.minimum_threshold

        product_info = {
            "name": offer.product.name if offer.product else "Plat KemTchop",
            "image_url": offer.product.image_url if offer.product else reel.image_url
        }

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
        "id": reel.id if hasattr(reel, 'id') else 0,
        "title": reel.title or product_info["name"],
        "video_url": reel.video_url,
        "image_url": reel.image_url,
        "daily_offer_id": str(offer.id) if offer else None,
        "product": product_info,
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
    ✅ Retourne les Reels actifs + Auto-génère des Reels pour les produits avec vidéo.
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
                seen_offer_ids.add(reel.daily_offer_id)
            result.append(_map_to_response(reel, reel.daily_offer))

        # 2. AUTO-REELS : Trouver les offres du jour dont le produit a une vidéo
        # mais qui n'ont pas encore de Reel marketing.
        # MODIF: On inclut aussi les produits avec vidéo qui n'ont pas d'offre active
        # pour assurer la visibilité immédiate après upload admin.
        auto_offers = (
            db.query(DailyOffer)
            .join(Product)
            .filter(Product.video_url != None)
            .filter(DailyOffer.status.in_(["proposed", "reservation", "confirmed", "cooking"]))
            .filter(~DailyOffer.id.in_(seen_offer_ids))
            .all()
        )

        for offer in auto_offers:
            virtual_reel = Reel(
                id=0,
                title=offer.product.name,
                video_url=offer.product.video_url,
                image_url=offer.product.image_url,
                daily_offer_id=offer.id
            )
            result.append(_map_to_response(virtual_reel, offer))

        # 3. PRODUITS AVEC VIDÉO SANS OFFRES (Nouveaux uploads)
        products_with_video = (
            db.query(Product)
            .filter(Product.video_url != None)
            .filter(~Product.id.in_([o.product_id for o in auto_offers]))
            .all()
        )

        for p in products_with_video:
            # Vérifier si on a déjà un reel pour ce produit via ses offres
            if any(r['product']['name'] == p.name for r in result):
                continue

            virtual_reel = Reel(
                id=0,
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
