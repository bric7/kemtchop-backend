# app/routes/products.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.entities.product import Product
from app.auth import check_permission

router = APIRouter(prefix="/products", tags=["Products"])


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    price_solo: Optional[float] = None
    price_duo: Optional[float] = None
    price_family: Optional[float] = None
    family_size: Optional[int] = None
    complements: Optional[str] = None
    is_hero: Optional[bool] = False


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    price_solo: Optional[float] = None
    price_duo: Optional[float] = None
    price_family: Optional[float] = None
    family_size: Optional[int] = None
    complements: Optional[str] = None
    is_hero: Optional[bool] = None

    class Config:
        from_attributes = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    price_solo: Optional[float] = None
    price_duo: Optional[float] = None
    price_family: Optional[float] = None
    family_size: Optional[int] = None
    complements: Optional[str] = None
    is_hero: Optional[bool] = None


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    """✅ Mettre à jour un produit"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    """✅ Supprimer un produit"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    db.delete(product)
    db.commit()
    return {"status": "success", "message": f"Produit {product_id} supprimé"}


@router.get("/", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    """✅ Liste tous les produits"""
    return db.query(Product).order_by(Product.name).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """✅ Détail d'un produit"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    return product


@router.post("/", status_code=201, response_model=ProductResponse)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products")),
):
    """✅ Créer un nouveau produit"""
    new_product = Product(
        name=data.name,
        description=data.description,
        category=data.category,
        image_url=data.image_url,
        price=data.price,
        price_solo=data.price_solo,
        price_duo=data.price_duo,
        price_family=data.price_family,
        family_size=data.family_size,
        complements=data.complements,
        is_hero=data.is_hero,
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product



