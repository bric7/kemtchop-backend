# app/routes/reels.py - VERSION FALLBACK
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.entities.product import Product

router = APIRouter(prefix="/reels", tags=["Reels"])


class ReelResponse(BaseModel):
    id: int
    product_name: str
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ReelResponse])
def get_reels(db: Session = Depends(get_db)):
    """
    ✅ Retourne les produits pour la section Reels.
    Priorité : produits avec video_url, sinon ceux avec image_url.
    """
    # Essayer d'abord les produits avec vidéo
    try:
        products_with_video = (
            db.query(Product)
            .filter(Product.video_url.isnot(None))
            .order_by(Product.id.desc())
            .limit(10)
            .all()
        )
        if products_with_video:
            return [
                ReelResponse(
                    id=p.id,
                    product_name=p.name,
                    video_url=p.video_url,
                    image_url=p.image_url,
                    category=p.category,
                )
                for p in products_with_video
            ]
    except Exception:
        pass  # Colonne video_url n'existe pas encore

    # Fallback : produits avec image
    products = (
        db.query(Product)
        .filter(Product.image_url.isnot(None))
        .order_by(Product.id.desc())
        .limit(10)
        .all()
    )

    return [
        ReelResponse(
            id=p.id,
            product_name=p.name,
            video_url=None,
            image_url=p.image_url,
            category=p.category,
        )
        for p in products
    ]