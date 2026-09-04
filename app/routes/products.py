# app/routes/products.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.entities.product import Product
from app.entities.reel import Reel
import uuid
from app.auth import check_permission

router = APIRouter(prefix="/products", tags=["Products"])


# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
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
    video_url: Optional[str] = None
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
    video_url: Optional[str] = None
    price: Optional[float] = None
    price_solo: Optional[float] = None
    price_duo: Optional[float] = None
    price_family: Optional[float] = None
    family_size: Optional[int] = None
    complements: Optional[str] = None
    is_hero: Optional[bool] = None


# ============================================================
# 📱 ENDPOINTS PUBLICS (MOBILE)
# ============================================================

# ✅ 1. ROUTE SPÉCIFIQUE : Doit être AVANT /{product_id} pour éviter le conflit 422 !
@router.get("/catalogue")
def get_catalogue(db: Session = Depends(get_db)):
    """✅ Liste tous les produits pour le catalogue mobile (format adapté)"""
    products = db.query(Product).all()
    result = []
    for p in products:
        result.append({
            "id": int(p.id),
            "name": str(p.name),
            "price": float(p.price) if p.price else 2500.0,
            "image_url": str(p.image_url) if p.image_url else "https://via.placeholder.com/150",
            "video_url": str(p.video_url) if p.video_url else None,
            "category": str(p.category) if p.category else "Général",
            "complements": str(p.complements) if p.complements else "Standard",
            # Champs requis par le frontend React Native
            "isCatalogueProduct": True,
            "status": "catalogue",
            "product": {
                "id": int(p.id),
                "name": str(p.name),
                "image_url": str(p.image_url) if p.image_url else "https://via.placeholder.com/150",
                "video_url": str(p.video_url) if p.video_url else None,
                "category": str(p.category) if p.category else "Général",
                "complements": str(p.complements) if p.complements else "Standard",
            }
        })
    return result


@router.get("/", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    """✅ Liste tous les produits (format admin/standard)"""
    return db.query(Product).order_by(Product.name).all()


# ✅ 2. ROUTE DYNAMIQUE : Doit être APRÈS les routes spécifiques
@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """✅ Détail d'un produit"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    return product


# ============================================================
# 👑 ENDPOINTS ADMIN
# ============================================================

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

    # ✅ Auto-création de Reel si vidéo présente
    if new_product.video_url:
        new_reel = Reel(
            id=uuid.uuid4(),
            title=new_product.name,
            product_name=new_product.name,
            video_url=new_product.video_url,
            image_url=new_product.image_url,
            category=new_product.category,
            price=new_product.price,
            is_active=True
        )
        db.add(new_reel)
        db.commit()

    return new_product


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

    # ✅ Sync Reel si la vidéo a été mise à jour ou ajoutée
    if 'video_url' in update_data and update_data['video_url']:
        existing_reel = db.query(Reel).filter(Reel.product_name == product.name).first()
        if not existing_reel:
            new_reel = Reel(
                id=uuid.uuid4(),
                title=product.name,
                product_name=product.name,
                video_url=product.video_url,
                image_url=product.image_url,
                category=product.category,
                price=product.price,
                is_active=True
            )
            db.add(new_reel)
        else:
            existing_reel.video_url = product.video_url
            if product.image_url:
                existing_reel.image_url = product.image_url
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