# app/routes/recipes.py
# ============================================================
# 📖 KEMTCHOP - Ingénierie Culinaire & Bibliothèque des Recettes
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.product import Product
from app.entities.ingredient import Ingredient
from app.entities.recipe import ProductIngredient
from app.schemas.recipe import RecipeUpdate, ProductIngredientResponse
from app.auth import check_permission

router = APIRouter(
    prefix="/recipes",
    tags=["Ingénierie & Recettes (R&D)"]
)

# ============================================================
# 🗄️ CONSULTATION DE LA BIBLIOTHÈQUE
# ============================================================

@router.get("/", status_code=status.HTTP_200_OK)
def get_all_recipes(db: Session = Depends(get_db)):
    """✅ Récupère toutes les recettes (produits) du catalogue"""
    return db.query(Product).order_by(Product.name.asc()).all()


@router.get("/{product_id}", status_code=status.HTTP_200_OK)
def get_recipe(product_id: int, db: Session = Depends(get_db)):
    """✅ Fiche technique d'un produit avec ses ingrédients"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Produit introuvable."
        )

    # Préparation de la réponse avec les détails des ingrédients
    ingredients = []
    for ri in product.recipe_ingredients:
        ingredients.append({
            "id": ri.id,
            "ingredient_id": ri.ingredient_id,
            "ingredient_name": ri.ingredient.name,
            "ingredient_unit": ri.ingredient.unit,
            "quantity_per_portion": ri.quantity_per_portion
        })

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "price": product.price,
        "ingredients": ingredients
    }

# ============================================================
# 🧪 GESTION DES COMPOSITIONS (Recettes)
# ============================================================

@router.put("/{product_id}/ingredients", status_code=status.HTTP_200_OK)
def update_product_recipe(
    product_id: int,
    recipe_data: RecipeUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products"))
):
    """✅ Met à jour la liste des ingrédients pour un produit (remplace l'existante)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    # 1. Supprimer l'ancienne composition
    db.query(ProductIngredient).filter(ProductIngredient.product_id == product_id).delete()

    # 2. Ajouter les nouveaux ingrédients
    for item in recipe_data.ingredients:
        # Vérifier que l'ingrédient existe
        ing = db.query(Ingredient).filter(Ingredient.id == item.ingredient_id).first()
        if not ing:
            raise HTTPException(status_code=400, detail=f"L'ingrédient {item.ingredient_id} n'existe pas")

        new_ri = ProductIngredient(
            product_id=product_id,
            ingredient_id=item.ingredient_id,
            quantity_per_portion=item.quantity_per_portion
        )
        db.add(new_ri)

    db.commit()
    return {"status": "success", "message": "Recette mise à jour avec succès"}

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_data: dict,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products"))
):
    """✅ Crée un nouveau produit dans le catalogue technique"""
    existing = db.query(Product).filter(Product.name == recipe_data.get("name")).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce produit existe déjà.")
    
    new_product = Product(
        name=recipe_data.get("name"),
        description=recipe_data.get("description", ""),
        price=recipe_data.get("price", 0),
        category=recipe_data.get("category", "Général"),
        is_hero=recipe_data.get("is_hero", False)
    )
    
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    return {"status": "success", "product_id": new_product.id}
