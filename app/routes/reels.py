# app/routes/reels.py
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
    ✅ Retourne les produits qui ont une vidéo (reels).
    Utilisé par la section Reels de la home mobile.
    """
    products = (
        db.query(Product)
        .filter(Product.video_url.isnot(None))
        .order_by(Product.id.desc())
        .limit(10)
        .all()
    )

    return [
        ReelResponse(
            id=p.id,
            product_name=p.name,
            video_url=p.video_url,
            image_url=p.image_url,
            category=p.category,
        )
        for p in products
    ]