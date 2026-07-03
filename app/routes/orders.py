# app/routes/orders.py
# ============================================================
# 📦 ROUTES COMMANDES - KemTchop API
# ============================================================

import datetime
from datetime import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Header, Query
from slowapi import Limiter
from slowapi.util import get_remote_address

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Order, User
from app.auth import get_current_user, check_permission
from app.services.expo_push import ExpoPushService

# ============================================================
# 🔧 CONFIG
# ============================================================
router = APIRouter()
logger = logging.getLogger("kemtchop")
limiter = Limiter(key_func=get_remote_address)

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
from pydantic import BaseModel

class OrderCreate(BaseModel):
    customer_name: str
    product_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    portion_size: str
    delivery_date: str 
    delivery_time: str 
    complement: Optional[str] = None
    affiliate_code: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    product_name: str
    customer_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    portion_size: str
    delivery_date: str
    delivery_time: str
    complement: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    affiliate_code: Optional[str] = None
    class Config:
        from_attributes = True

# ============================================================
# 🛠️ UTILITAIRES
# ============================================================
def validate_cameroon_phone(phone: str) -> bool:
    import re
    clean = re.sub(r'\D', '', phone)
    return bool(re.match(r'^(237)?6[0-9]{8}$', clean))

# ============================================================
# 📦 CRUD COMMANDES
# ============================================================
@router.post("/create")
@limiter.limit("30 per minute")
async def create_order(request: Request, order_data: dict, db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")):
    try:
        required = ["customer_name", "product_name", "phone", "zone", "total_amount", "deposit_amount"]
        for field in required:
            if not order_data.get(field):
                raise HTTPException(status_code=400, detail=f"Champ requis manquant : {field}")
        if not validate_cameroon_phone(order_data.get("phone", "")):
            raise HTTPException(status_code=400, detail="Numéro invalide")
        
        if idempotency_key:
            existing = db.query(Order).filter(Order.idempotency_key == idempotency_key).first()
            if existing:
                logger.info(f"🔄 Requête idempotente ignorée: {idempotency_key}")
                return {"status": "success", "order_id": existing.id, "duplicate": True}
        
        ref_code = order_data.get("affiliate_code")
        new_order = Order(
            customer_name=order_data["customer_name"], product_name=order_data["product_name"],
            phone=order_data["phone"], zone=order_data["zone"],
            total_amount=float(order_data["total_amount"]), deposit_amount=float(order_data["deposit_amount"]),
            portion_size=order_data.get("portion_size"), delivery_date=order_data.get("delivery_date"),
            delivery_time=order_data.get("delivery_time"), complement=order_data.get("complement"),
            affiliate_code=ref_code, affiliate_payout_phone=order_data.get("affiliate_payout_phone"),
            status="en_attente", idempotency_key=idempotency_key
        )
        db.add(new_order)
        
        if ref_code:
            ambassador = db.query(User).filter(User.affiliate_code == ref_code, User.is_affiliate == True).first()
            if ambassador:
                commission = float(order_data["total_amount"]) * 0.15
                ambassador.pending_commissions = (ambassador.pending_commissions or 0) + commission
                logger.info(f"💰 Commission +{commission} FCFA pour {ref_code}")
        
        db.commit()
        db.refresh(new_order)
        
        if new_order.phone:
            client = db.query(User).filter(User.phone == new_order.phone).first()
            if client and client.expo_push_token:
                import asyncio
                asyncio.create_task(ExpoPushService.send_notification(
                    expo_token=client.expo_push_token, title="KemTchop 🍳",
                    body=f"Votre commande de {new_order.product_name} est confirmée !",
                    data={"orderId": new_order.id, "type": "order_confirmed"}
                ))
        
        logger.info(f"✅ Commande #{new_order.id} créée")
        return {"status": "success", "order_id": new_order.id, "duplicate": False}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur création commande : {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Erreur lors de la création")

@router.get("/", response_model=list[OrderResponse])
@limiter.limit("100 per minute")
def list_orders(request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    return db.query(Order).filter(Order.phone == current_user["phone"]).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/my-orders")
@limiter.limit("60 per minute")
def get_my_orders(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_phone = current_user.get("phone")
    if not user_phone:
        logger.warning("🚨 Tentative d'accès sans téléphone dans le token")
        raise HTTPException(status_code=403, detail="Identifiant manquant dans la session")
    
    import re
    clean_phone = re.sub(r'\D', '', user_phone)
    
    orders = db.query(Order).filter(Order.phone == clean_phone).order_by(Order.created_at.desc()).all()
    logger.info(f"📋 {len(orders)} commandes chargées pour {clean_phone}")
    return orders

@router.patch("/admin/{order_id}/status")
@limiter.limit("30 per minute")
async def update_order_status(request: Request, order_id: int, new_status: str, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("orders"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    old = order.status
    order.status = new_status
    db.commit()
    logger.info(f"📦 Commande #{order_id} : {old} → {new_status}")
    return {"status": "success", "new_status": order.status}

@router.patch("/admin/{order_id}/pay-commission")
@limiter.limit("20 per minute")
async def pay_commission(request: Request, order_id: int, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    order.commission_paid = True
    db.commit()
    logger.info(f"💸 Commission payée pour commande #{order_id}")
    return {"status": "success", "message": "Commission marquée comme payée"}

@router.get("/admin", response_model=list[OrderResponse])
@limiter.limit("60 per minute")
async def get_admin_orders(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("orders")), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    orders = db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": o.id, "product_name": o.product_name, "customer_name": o.customer_name,
            "phone": o.phone, "zone": o.zone, "total_amount": float(o.total_amount or 0),
            "deposit_amount": float(o.deposit_amount or 0), "status": o.status,
            "portion_size": o.portion_size, "delivery_date": o.delivery_date,
            "delivery_time": o.delivery_time, "complement": o.complement,
            "created_at": str(o.created_at) if o.created_at else None, "affiliate_code": o.affiliate_code,
        }
        for o in orders
    ]

# app/routes/orders.py - EXTRAITS CLÉS
# ============================================================
# 📦 CRÉATION DE COMMANDE (référence DailyMenu)
# ============================================================
@router.post("/create")
async def create_order(
    order_data: OrderCreate,  # Contient maintenant daily_menu_id
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
):
    # 1. Valider le DailyMenu existe et accepte les commandes
    daily_menu = db.query(DailyMenu).filter(
        DailyMenu.id == order_data.daily_menu_id
    ).first()
    
    if not daily_menu:
        raise HTTPException(status_code=404, detail="Menu non trouvé")
    
    if not daily_menu.is_accepting_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Ce menu n'accepte plus de commandes (statut: {daily_menu.status})"
        )
    
    # 2. Vérifier la capacité
    if daily_menu.remaining_capacity is not None:
        portions_to_add = order_data.portions if order_data.mode == "portion" else daily_menu.minimum_production
        if portions_to_add > daily_menu.remaining_capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Capacité insuffisante : {daily_menu.remaining_capacity} places restantes"
            )
    
    # 3. Créer la commande (référence DailyMenu, pas Product)
    new_order = Order(
        daily_menu_id=daily_menu.id,  # ← NOUVEAU
        product_id=daily_menu.product_id,  # ← Pour compatibilité analytics
        mode=order_data.mode,  # "pack" ou "portion"
        portions=order_data.portions,
        price_paid=daily_menu.pack_price if order_data.mode == "pack" else daily_menu.individual_price,
        # ... autres champs
    )
    
    # 4. Mettre à jour le compteur du DailyMenu
    daily_menu.reserved_portions += (
        daily_menu.minimum_production if order_data.mode == "pack" else order_data.portions
    )
    
    # 5. Transition auto si seuil atteint
    if (daily_menu.status == "PREORDER_OPEN" and 
        daily_menu.reserved_portions >= daily_menu.minimum_production):
        daily_menu.status = "PRODUCTION_CONFIRMED"
        daily_menu.launched_at = datetime.utcnow()
    
    db.commit()
    
    return {"status": "success", "order_id": new_order.id, "menu_status": daily_menu.status}
