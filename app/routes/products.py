# app/routes/products.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.entities.product import Product
from app.auth import check_permission

router = APIRouter(prefix="/products", tags=["Products"])


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    complements: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    """✅ Liste tous les produits du catalogue"""
    products = db.query(Product).order_by(Product.name).all()
    return products


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """✅ Détail d'un produit"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    return product