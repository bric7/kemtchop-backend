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
from app.enums import ProductionStatus

logger = logging.getLogger("kemtchop.reels")
router = APIRouter(prefix="/reels", tags=["Reels"])

class ReelProductInfo(BaseModel):
    name: str
    image_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ReelResponse(BaseModel):
    # ✅ CORRECTION CRITIQUE : UUID au lieu de int
    id: UUID
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
    reserved_portions: int = 0
    minimum_threshold: int = 0

    # 🎨 UI Helpers (Machine d'État v3.0)
    button_label: str = "VOIR"
    urgency_message: Optional[str] = None

    # ✅ Config Pydantic V2 moderne
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[ReelResponse])
def get_reels(db: Session = Depends(get_db)):
    """
    ✅ Retourne les Reels actifs avec l'état en temps réel de la production liée.
    Suit la Machine d'État KemTchop v3.0.
    """
    try:
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
            urgency_message = "Découvrez ce plat !"
            is_threshold_reached = False
            product_info = None
            status = "proposed"
            target_date = None
            price_per_unit = None
            reserved_portions = 0
            minimum_threshold = 0

            if offer:
                status = offer.status
                is_threshold_reached = offer.is_threshold_reached
                target_date = offer.target_date
                price_per_unit = offer.price_per_unit
                reserved_portions = offer.reserved_portions
                minimum_threshold = offer.minimum_threshold
                
                product_info = ReelProductInfo(
                    name=offer.product.name if offer.product else "Plat KemTchop",
                    image_url=offer.product.image_url if offer.product else None
                )

                # 🧠 Logique de Label Dynamique v3.0 (Ton excellente logique)
                status_lower = status.lower() if status else "proposed"
                
                if status_lower in ["proposed", "reservation"]:
                    button_label = "RÉSERVER"
                    remaining = max(0, minimum_threshold - reserved_portions)
                    urgency_message = f"🔥 Encore {remaining} portions"
                elif status_lower == "confirmed":
                    button_label = "COMMANDER"
                    urgency_message = "✅ Production garantie !"
                elif status_lower == "cooking":
                    button_label = "👨‍🍳 EN CUISINE"
                    urgency_message = "Préparation en cours"
                elif status_lower in ["ready", "delivered"]:
                    button_label = "✅ LIVRÉ"
                    urgency_message = "Service terminé"
                elif status_lower == "delivering":
                    button_label = "🚚 EN ROUTE"
                    urgency_message = "En cours de livraison"

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
                reserved_portions=reserved_portions,
                minimum_threshold=minimum_threshold,
                button_label=button_label,
                urgency_message=urgency_message
            ))

        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération reels : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne serveur lors de la récupération des reels")