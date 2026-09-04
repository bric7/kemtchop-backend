from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.entities.ingredient import Ingredient
from app.entities.stock_movement import StockMovement
from app.schemas.ingredient import IngredientCreate, IngredientUpdate, IngredientResponse
from app.auth import check_permission
from app.services.notification_service import NotificationService
from app.entities.user import User

router = APIRouter(
    prefix="/inventory",
    tags=["Gestion des Stocks & Ingrédients"]
)

@router.get("/ingredients", response_model=List[IngredientResponse])
def get_ingredients(db: Session = Depends(get_db)):
    """Liste tous les ingrédients en stock"""
    return db.query(Ingredient).all()

@router.post("/ingredients", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    ingredient: IngredientCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_inventory"))
):
    """Ajoute un nouvel ingrédient au catalogue"""
    existing = db.query(Ingredient).filter(Ingredient.name == ingredient.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cet ingrédient existe déjà")

    db_ingredient = Ingredient(**ingredient.model_dump())
    db.add(db_ingredient)
    db.commit()
    db.refresh(db_ingredient)
    return db_ingredient

@router.patch("/ingredients/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(
    ingredient_id: int,
    update_data: IngredientUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_inventory"))
):
    """Met à jour les informations d'un ingrédient"""
    db_ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not db_ingredient:
        raise HTTPException(status_code=404, detail="Ingrédient non trouvé")

    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_ingredient, key, value)

    db.commit()
    db.refresh(db_ingredient)
    return db_ingredient

@router.post("/stock-movement", status_code=status.HTTP_201_CREATED)
def add_stock_movement(
    ingredient_id: int,
    quantity: float,
    movement_type: str, # PURCHASE, WASTE, ADJUSTMENT
    notes: str = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_inventory"))
):
    """Enregistre un mouvement de stock et met à jour la quantité actuelle"""
    db_ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not db_ingredient:
        raise HTTPException(status_code=404, detail="Ingrédient non trouvé")

    # Créer le mouvement
    movement = StockMovement(
        ingredient_id=ingredient_id,
        quantity=quantity,
        movement_type=movement_type,
        notes=notes
    )

    # Mettre à jour le stock actuel
    db_ingredient.current_quantity += quantity

    db.add(movement)
    db.commit()

    # Vérification du stock bas après mouvement
    if db_ingredient.current_quantity <= db_ingredient.min_threshold:
        # Récupérer les admins ayant la permission manage_inventory
        admins = db.query(User).filter(
            User.permissions.contains("manage_inventory"),
            User.expo_push_token.isnot(None)
        ).all()

        tokens = [admin.expo_push_token for admin in admins]
        if tokens:
            import asyncio
            asyncio.create_task(NotificationService.notify_low_stock(
                ingredient_name=db_ingredient.name,
                current_quantity=db_ingredient.current_quantity,
                unit=db_ingredient.unit,
                admin_tokens=tokens
            ))

    return {"status": "success", "new_quantity": db_ingredient.current_quantity}
