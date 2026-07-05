# app/routes/recipes.py
# ============================================================
# 📖 KEMTCHOP - Ingénierie Culinaire & Bibliothèque des Recettes
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.product import Product  # On réutilise ton entité de base de données
from app.auth import check_permission
from app.schemas.collective_pot import CollectivePotResponse # Ou tes schémas dédiés si tu en as

router = APIRouter(
    prefix="/recipes",
    tags=["Ingénierie & Recettes (R&D)"]
)

# ============================================================
# 🗄️ CONSULTATION DE LA BIBLIOTHÈQUE (SQLAlchemy)
# ============================================================

@router.get("/", status_code=status.HTTP_200_OK)
def get_all_recipes(db: Session = Depends(get_db)):
    """✅ Récupère toutes les recettes réelles stockées en base de données"""
    return db.query(Product).order_by(Product.product_name.asc()).all()


@router.get("/{recipe_id}", status_code=status.HTTP_200_OK)
def get_recipe(recipe_id: str, db: Session = Depends(get_db)):
    """✅ Fiche technique d'une recette spécifique"""
    recipe = db.query(Product).filter(Product.id == recipe_id).first()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Recette introuvable dans la bibliothèque R&D."
        )
    return recipe


# ============================================================
# 🧪 INGÉNIERIE & CRÉATION (Sécurisée par Permissions)
# ============================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_data: dict, # Remplaçable par ton schéma RecipeCreate ou ProductCreate
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products"))
):
    """✅ Persiste une nouvelle recette dans le catalogue technique de l'usine"""
    
    # Éviter les doublons sur le nom de la recette
    existing = db.query(Product).filter(Product.product_name == recipe_data.get("name")).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Cette recette existe déjà dans la bibliothèque."
        )
    
    # Hydratation de l'entité SQL
    new_recipe = Product(
        product_name=recipe_data.get("name"),
        description=recipe_data.get("description", ""),
        price=recipe_data.get("price", 0),
        image_url=recipe_data.get("image_url", ""),
        category=recipe_data.get("category", "Général"),
        is_available=True
    )
    
    db.add(new_recipe)
    db.commit()
    db.refresh(new_recipe)
    
    return {
        "status": "success",
        "recipe_id": new_recipe.id,
        "message": f"Recette '{new_recipe.product_name}' sauvegardée de manière persistante."
    }