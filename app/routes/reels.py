# app/routes/reels.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Union
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
    id: Optional[Union[int, UUID, str]] = None
    name: str
    image_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ReelResponse(BaseModel):
    id: Union[int, UUID, str]
    type: str = "product"
    item_type: str = "product"
    reel_category: str = "CATALOG_PRODUCT"
    is_catalogue: bool = True
    sides: List[str] = []
    offer_date: Optional[date] = None
    offer_id: Optional[Union[int, UUID, str]] = None
    product_id: Optional[Union[int, UUID, str]] = None
    title: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    daily_offer_id: Optional[Union[int, UUID, str]] = None
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

def _map_to_response(reel, offer, db: Session = None) -> dict:
    """Helper pour transformer un Reel et son Offre en ReelResponse"""
    product_name = "Plat KemTchop"
    product_id = None

    # 1. Résolution de l'offre et du produit associé
    if offer and offer.product:
        product_name = offer.product.name
        product_id = offer.product.id
    elif reel.daily_offer and reel.daily_offer.product:
        offer = reel.daily_offer
        product_name = offer.product.name
        product_id = offer.product.id
    elif hasattr(reel, 'product_name') and reel.product_name and db:
        product_name = reel.product_name
        prod = db.query(Product).filter(Product.name.ilike(product_name)).first()
        if prod:
            product_id = prod.id
            if not offer:
                # Chercher une offre active pour ce produit
                offer = db.query(DailyOffer).filter(DailyOffer.product_id == prod.id).first()
                if offer and offer.product:
                    product_id = offer.product.id

    if not product_id and db:
        # Essayer de faire correspondre par titre du reel ou nom de produit
        search_term = reel.title or reel.product_name
        if search_term:
            prod = db.query(Product).filter(Product.name.ilike(f"%{search_term}%")).first()
            if prod:
                product_id = prod.id
                product_name = prod.name
                if not offer:
                    offer = db.query(DailyOffer).filter(DailyOffer.product_id == prod.id).first()

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

    # 4. Accompagnements (sides) et type d'élément
    sides = []
    raw_complements = None
    if offer and offer.product and hasattr(offer.product, 'complements'):
        raw_complements = offer.product.complements
    elif offer and hasattr(offer, 'complements'):
        raw_complements = offer.complements

    if raw_complements:
        if isinstance(raw_complements, list):
            sides = raw_complements
        elif isinstance(raw_complements, str):
            sides = [s.strip() for s in raw_complements.split(",") if s.strip()]

    if not sides:
        sides = ["Riz", "Plantain", "Bâton de manioc"]

    item_type = "offer" if offer else "product"
    is_catalogue = not bool(offer)
    offer_date = target_date if offer else None

    # Calcul précis de reel_category
    today_str = date.today().isoformat()
    if offer and target_date:
        target_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
        if target_str == today_str:
            reel_category = "DAILY_MENU"
        else:
            reel_category = "FUTURE_RESERVATION"
    else:
        reel_category = "CATALOG_PRODUCT"

    return {
        "id": reel.id if hasattr(reel, 'id') and reel.id else uuid.uuid4(),
        "type": item_type,
        "item_type": item_type,
        "reel_category": reel_category,
        "is_catalogue": is_catalogue,
        "sides": sides,
        "offer_date": offer_date,
        "offer_id": offer.id if offer else None,
        "product_id": product_id,
        "title": getattr(reel, 'title', None) or product_name,
        "video_url": video_url,
        "image_url": image_url,
        "daily_offer_id": offer.id if offer else None,
        "product": {
            "id": product_id,
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
    Dédoublonnage strict par video_url pour éviter les répétitions sur mobile.
    """
    try:
        result = []
        seen_video_urls = set()
        seen_offer_ids = set()
        seen_product_names = set()

        # 1. Récupérer les Reels créés explicitement
        reels = (
            db.query(Reel)
            .options(joinedload(Reel.daily_offer).joinedload(DailyOffer.product))
            .filter(Reel.is_active == True)
            .order_by(Reel.priority.desc(), Reel.created_at.desc())
            .all()
        )

        for reel in reels:
            resp = _map_to_response(reel, reel.daily_offer, db)
            v_url = resp.get("video_url")
            if v_url and v_url not in seen_video_urls:
                seen_video_urls.add(v_url)
                if reel.daily_offer_id:
                    seen_offer_ids.add(str(reel.daily_offer_id))
                if resp.get('product') and resp['product'].get('name'):
                    seen_product_names.add(resp['product']['name'])
                result.append(resp)

        # 2. AUTO-REELS : Offres actives avec vidéo (Produit ou Offre) sans Reel explicite
        auto_offers = (
            db.query(DailyOffer)
            .join(Product)
            .options(joinedload(DailyOffer.product))
            .filter((Product.video_url != None) | (DailyOffer.video_url != None))
            .filter(DailyOffer.status.in_(["proposed", "reservation", "confirmed", "cooking"]))
            .filter(~DailyOffer.id.in_(seen_offer_ids))
            .all()
        )

        for offer in auto_offers:
            virtual_reel = Reel(
                id=uuid.uuid4(),
                title=offer.product.name,
                product_name=offer.product.name,
                video_url=offer.video_url or offer.product.video_url,
                image_url=offer.image_url or offer.product.image_url,
                daily_offer_id=offer.id
            )
            resp = _map_to_response(virtual_reel, offer, db)
            v_url = resp.get("video_url")
            if v_url and v_url not in seen_video_urls:
                seen_video_urls.add(v_url)
                seen_offer_ids.add(str(offer.id))
                if resp.get('product') and resp['product'].get('name'):
                    seen_product_names.add(resp['product']['name'])
                result.append(resp)

        # 3. PRODUITS AVEC VIDÉO SANS OFFRES (Nouveaux uploads)
        products_with_video = (
            db.query(Product)
            .filter(Product.video_url != None)
            .all()
        )

        for p in products_with_video:
            if p.name in seen_product_names or p.video_url in seen_video_urls:
                continue

            virtual_reel = Reel(
                id=uuid.uuid4(),
                title=p.name,
                product_name=p.name,
                video_url=p.video_url,
                image_url=p.image_url,
                daily_offer_id=None
            )
            resp = _map_to_response(virtual_reel, None, db)
            v_url = resp.get("video_url")
            if v_url and v_url not in seen_video_urls:
                seen_video_urls.add(v_url)
                result.append(resp)

        return result

    except Exception as e:
        logger.error(f"❌ Erreur récupération reels : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne serveur lors de la récupération des reels")
