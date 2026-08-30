# app/routes/reels.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import date

from app.database import get_db
from app.entities.product import Product
from app.entities.daily_offer import DailyOffer
from app.enums import ProductionStatus

router = APIRouter(prefix="/reels", tags=["Reels"])

class ReelResponse(BaseModel):
    id: int # Product ID
    product_name: str
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None

    # 🔥 Infos de conversion (DailyOffer)
    daily_offer_id: Optional[UUID] = None
    daily_offer_status: Optional[str] = None
    target_date: Optional[date] = None

    class Config:
        from_attributes = True

@router.get("/", response_model=List[ReelResponse])
def get_reels(db: Session = Depends(get_db)):
    """
    ✅ Retourne les vidéos Reels.
    Priorité absolue aux produits ayant une DailyOffer active (aujourd'hui ou futur).
    """
    today = date.today()

    # 1. Trouver les offres actives (non annulées et non terminées)
    active_offers = (
        db.query(DailyOffer)
        .options(joinedload(DailyOffer.product))
        .filter(
            DailyOffer.target_date >= today,
            DailyOffer.status.notin_([ProductionStatus.CANCELLED.value, ProductionStatus.COMPLETED.value])
        )
        .order_by(DailyOffer.target_date.asc())
        .all()
    )

    results = []
    seen_products = set()

    # 2. Transformer les offres en Reels (priorité)
    for offer in active_offers:
        if offer.product_id not in seen_products and offer.product.video_url:
            results.append(ReelResponse(
                id=offer.product.id,
                product_name=offer.product.name,
                video_url=offer.product.video_url,
                image_url=offer.product.image_url,
                category=offer.product.category,
                daily_offer_id=offer.id,
                daily_offer_status=offer.status,
                target_date=offer.target_date
            ))
            seen_products.add(offer.product_id)

    # 3. Compléter avec d'autres produits ayant des vidéos si nécessaire
    if len(results) < 10:
        others = (
            db.query(Product)
            .filter(Product.video_url.isnot(None))
            .filter(Product.id.notin_(list(seen_products) if seen_products else [-1]))
            .limit(10 - len(results))
            .all()
        )
        for p in others:
            results.append(ReelResponse(
                id=p.id,
                product_name=p.name,
                video_url=p.video_url,
                image_url=p.image_url,
                category=p.category
            ))

    return results
