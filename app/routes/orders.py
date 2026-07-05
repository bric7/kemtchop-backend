# app/routes/orders.py
# ============================================================
# 📦 ROUTES COMMANDES - KemTchop API (Version Simplifiée)
# ============================================================

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.collective_pot import CollectivePot
from app.entities.order import Order
from app.enums import ProductionStatus, OrderStatus  # ✅ Nos enums centralisés
from app.auth import get_current_user

logger = logging.getLogger("kemtchop.orders")
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/orders", tags=["Orders"])

# ============================================================
# 📋 PYDANTIC SCHEMAS (inline pour simplicité)
# ============================================================
from pydantic import BaseModel, Field

class OrderCreateRequest(BaseModel):
    collective_pot_id: str = Field(..., description="ID du menu du jour (UUID)")
    portions: int = Field(1, ge=1, le=10, description="Nombre de portions (1-10)")
    delivery_zone: str = Field(..., min_length=2, max_length=100)
    complement: Optional[str] = Field(None, max_length=200)
    affiliate_code: Optional[str] = Field(None)

class OrderResponse(BaseModel):
    id: int
    product_name: str
    customer_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    portions: int
    mode: str
    status: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================
# 📦 CRUD COMMANDES
# ============================================================

@router.post("/create", response_model=dict, status_code=201)
@limiter.limit("30/minute")
async def create_order(
    request: Request,
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: dict = Depends(get_current_user)
):
    """✅ Créer une nouvelle commande (avec idempotence)"""
    
    # 1. Vérifier que le CollectivePot existe et accepte les commandes
    menu = db.query(CollectivePot).filter(
        CollectivePot.id == payload.collective_pot_id
    ).first()
    
    if not menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    
    # ✅ Utiliser la propriété type-safe de l'enum
    if not menu.is_accepting_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Ce menu n'accepte plus de commandes (statut: {menu.status})"
        )
    
    # 2. Vérifier la capacité restante
    if menu.remaining_capacity and payload.portions > menu.remaining_capacity:
        raise HTTPException(
            status_code=400,
            detail=f"Capacité insuffisante : {menu.remaining_capacity} places restantes"
        )
    
    # 3. Vérifier l'idempotence (éviter les doublons)
    if idempotency_key:
        existing = db.query(Order).filter(
            Order.idempotency_key == idempotency_key
        ).first()
        if existing:
            logger.info(f"🔄 Requête idempotente ignorée: {idempotency_key}")
            return {
                "status": "success",
                "order_id": existing.id,
                "duplicate": True,
                "message": "Commande déjà enregistrée"
            }
    
    # 4. Calculer les prix
    price_per_portion = menu.individual_price
    total_amount = price_per_portion * payload.portions
    deposit_amount = round(total_amount * 0.40)  # 40% d'acompte
    
    # 5. Créer la commande
    new_order = Order(
        collective_pot_id=menu.id,
        product_id=menu.product_id,  # Pour compatibilité analytics
        customer_name=current_user.get("name", "Client"),
        phone=current_user.get("phone", ""),
        zone=payload.delivery_zone,
        total_amount=total_amount,
        deposit_amount=deposit_amount,
        portions=payload.portions,
        mode="portion",  # Par défaut; pourrait être "pack" si logique métier
        complement=payload.complement,
        affiliate_code=payload.affiliate_code,
        status=OrderStatus.PENDING.value,  # ✅ Utiliser la valeur de l'enum
        delivery_date=menu.occurrence_date.strftime("%Y-%m-%d") if menu.occurrence_date else "",
        delivery_time=menu.cutoff_time.strftime("%H:%M") if menu.cutoff_time else "18:00",
        idempotency_key=idempotency_key
    )
    
    # 6. Transaction atomique : commande + incrément du compteur
    try:
        db.add(new_order)
        db.flush()  # Génère l'ID sans commit
        
        # Incrémenter le compteur du menu
        menu.reserved_portions += payload.portions
        
        # Transition auto si seuil atteint
        if menu.status == ProductionStatus.PUBLISHED.value and menu.reserved_portions >= menu.minimum_production:
            menu.status = ProductionStatus.CONFIRMED.value
            menu.launched_at = datetime.utcnow()
            logger.info(
                "🚀 Seuil atteint pour %s : %d/%d portions → statut CONFIRMED",
                menu.product.name,
                menu.reserved_portions,
                menu.minimum_production
            )
        
        db.commit()
        db.refresh(new_order)
        
        logger.info("✅ Commande #%d créée pour %s", new_order.id, new_order.phone)
        
        return {
            "status": "success",
            "order_id": new_order.id,
            "duplicate": False,
            "deposit_amount": deposit_amount,
            "remaining_balance": total_amount - deposit_amount,
            "menu_status": menu.status
        }
        
    except Exception as e:
        db.rollback()
        logger.error("❌ Erreur création commande : %s", e)
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la commande")


@router.get("/my-orders", response_model=List[OrderResponse])
@limiter.limit("60/minute")
def get_my_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20
):
    """✅ Récupérer les commandes de l'utilisateur authentifié"""
    
    user_phone = current_user.get("phone")
    if not user_phone:
        raise HTTPException(status_code=403, detail="Identifiant manquant dans la session")
    
    orders = db.query(Order).filter(
        Order.phone == user_phone
    ).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    logger.info("📋 %d commandes chargées pour %s", len(orders), user_phone)
    return orders


@router.get("/{order_id}", response_model=OrderResponse)
@limiter.limit("100/minute")
def get_order_detail(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """✅ Détail d'une commande spécifique"""
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    # Vérifier que l'utilisateur a le droit de voir cette commande
    if order.phone != current_user.get("phone") and current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    return order


@router.patch("/{order_id}/status")
@limiter.limit("20/minute")
def update_order_status(
    request: Request,
    order_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(lambda: None)  # TODO: Ajouter check_permission("orders")
):
    """✅ Mettre à jour le statut d'une commande (admin/cuisine uniquement)"""
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    # Valider le nouveau statut via enum
    try:
        new_status_enum = OrderStatus(new_status)
    except ValueError:
        valid_values = [s.value for s in OrderStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Statut invalide. Valeurs acceptées : {valid_values}"
        )
    
    old_status = order.status
    order.status = new_status_enum.value
    order.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info("📦 Commande #%d : %s → %s", order_id, old_status, new_status)
    
    return {
        "status": "success",
        "order_id": order_id,
        "old_status": old_status,
        "new_status": new_status
    }