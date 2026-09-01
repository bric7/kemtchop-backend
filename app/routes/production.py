# app/routes/products.py
# ============================================================
# 🍽️ ROUTES CATALOGUE PRODUITS - KemTchop API
# ============================================================

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.product import Product

logger = logging.getLogger("kemtchop.products")
router = APIRouter(prefix="/products", tags=["Products"])


# ============================================================
# 📱 ENDPOINTS PUBLICS
# ============================================================
@router.get("/catalogue")
def get_product_catalogue(
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    db: Session = Depends(get_db)
):
    """
    ✅ Retourne le catalogue complet des produits réservables.
    Indépendant des DailyOffers et des dates.
    Retourne des dictionnaires pour éviter les erreurs de validation Pydantic 
    si certains champs optionnels n'existent pas dans le modèle Product.
    """
    query = db.query(Product)
    
    # Filtrer uniquement les produits actifs/réservables (si le champ existe)
    if hasattr(Product, 'is_active'):
        query = query.filter(Product.is_active == True)
    
    # Filtrer les produits "hero" (si le champ existe)
    if hasattr(Product, 'is_hero'):
        query = query.filter(Product.is_hero == True)
    
    if category and category != "Tout":
        query = query.filter(Product.category == category)
    
    products = query.order_by(Product.name.asc()).all()
    
    # Conversion manuelle en dictionnaire pour une robustesse maximale
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "name": p.name,
            "category": getattr(p, 'category', None),
            "image_url": getattr(p, 'image_url', None),
            "price": getattr(p, 'price', 2500),  # Valeur par défaut si manquante
            "complements": getattr(p, 'complements', "Standard"),  # Valeur par défaut
            "description": getattr(p, 'description', None),
            "isCatalogueProduct": True,  # Flag pour le frontend
            "status": "catalogue",
            "product": {
                "id": p.id,
                "name": p.name,
                "image_url": getattr(p, 'image_url', None),
                "category": getattr(p, 'category', None),
                "complements": getattr(p, 'complements', "Standard"),
            }
        })
    
    logger.info(f"🍽️ Catalogue : {len(result)} produits disponibles")
    return result