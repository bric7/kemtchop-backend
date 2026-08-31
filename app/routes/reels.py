# app/routes/reels.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import date

from app.database import get_db
from app.entities.reel import Reel
from app.entities.daily_offer import DailyOffer
from app.enums import ProductionStatus

router = APIRouter(prefix="/reels", tags=["Reels"])

class ReelProductInfo(BaseModel):
    name: str
    image_url: Optional[str] = None

class ReelResponse(BaseModel):
    id: int
    title: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None

    # 🔗 Liaison DailyOffer
    daily_offer_id: Optional[UUID] = None
    product: Optional[ReelProductInfo] = None
    status: Optional[str] = None
    is_threshold_reached: bool = False
    target_date: Optional[date] = None
    price_per_unit: Optional[float] = None

    # 🎨 UI Helpers (Machine d'État v3.0)
    button_label: str = "VOIR"
    urgency_message: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/", response_model=List[ReelResponse])
def get_reels(db: Session = Depends(get_db)):
    """
    ✅ Retourne les Reels actifs avec l'état en temps réel de la production liée.
    Suit la Machine d'État KemTchop v3.0.
    """
    reels = (
        db.query(Reel)
        .options(joinedload(Reel.daily_offer).joinedload(DailyOffer.product))
        .filter(Reel.is_active == True)
        .order_by(Reel.priority.desc(), Reel.created_at.desc())
        .all()
    )

    result = []
    for reel in reels:
        offer = reel.daily_offer

        # Valeurs par défaut
        button_label = "VOIR"
        urgency_message = None
        is_threshold_reached = False
        product_info = None
        status = None
        target_date = None
        price_per_unit = None

        if offer:
            status = offer.status
            is_threshold_reached = offer.is_threshold_reached
            target_date = offer.target_date
            price_per_unit = offer.price_per_unit
            product_info = ReelProductInfo(
                name=offer.product.name if offer.product else "Plat KemTchop",
                image_url=offer.product.image_url if offer.product else None
            )

            # 🧠 Logique de Label Dynamique v3.0
            if status in [ProductionStatus.PROPOSED, ProductionStatus.RESERVATION]:
                button_label = "RÉSERVER"
                urgency_message = f"Encore {offer.remaining_to_trigger} portions"
            elif status == ProductionStatus.CONFIRMED:
                button_label = "COMMANDER"
                urgency_message = "Production garantie !"
            elif status == ProductionStatus.COOKING:
                button_label = "👨‍🍳 EN CUISINE"
                urgency_message = "Préparation en cours"
            elif status == ProductionStatus.READY:
                button_label = "🍱 PRÊT"
                urgency_message = "C'est prêt !"
            elif status == ProductionStatus.DELIVERING:
                button_label = "🚚 EN ROUTE"
                urgency_message = "En cours de livraison"
            elif status == ProductionStatus.DELIVERED:
                button_label = "✅ LIVRÉ"
                urgency_message = "Service terminé"

        result.append(ReelResponse(
            id=reel.id,
            title=reel.title,
            video_url=reel.video_url,
            image_url=reel.image_url,
            daily_offer_id=offer.id if offer else None,
            product=product_info,
            status=status,
            is_threshold_reached=is_threshold_reached,
            target_date=target_date,
            price_per_unit=price_per_unit,
            button_label=button_label,
            urgency_message=urgency_message
        ))

    return result
