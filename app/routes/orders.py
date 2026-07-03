# app/routes/orders.py
# ============================================================
# 📦 UNIVERSE TRANSACTIONS & COMMANDES - KEMTCHOP API
# ============================================================

import logging
import re
from datetime import datetime
from typing import List, Optional
import asyncio

from fastapi import APIRouter, Request, Depends, HTTPException, status, Header, Query
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, User, DailyMenu
from app.auth import get_current_user, check_permission
from app.services.expo_push import ExpoPushService

logger = logging.getLogger("kemtchop.orders")
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/orders", tags=["Orders"])

# ============================================================
# 📋 PYDANTIC SCHEMAS (Contrats de Données)
# ============================================================

class OrderCreate(BaseModel):
    daily_menu_id: int
    customer_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    mode: str                      # "pack" (lancement) ou "portion" (individuelle)
    portions: int                  # Nombre de portions demandées
    portion_size: str              # Ex: "Standard", "XL"
    delivery_date: str 
    delivery_time: str 
    complement: Optional[str] = None
    affiliate_code: Optional[str] = None
    affiliate_payout_phone: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    daily_menu_id: int
    product_id: int
    customer_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    mode: str
    portions: int
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
# 🛠️ UTILS
# ============================================================

def validate_cameroon_phone(phone: str) -> str:
    """Nettoie et valide un numéro camerounais (MTN / Orange)"""
    clean = re.sub(r'\D', '', phone)
    if not re.match(r'^(237)?6[0-9]{8}$', clean):
        raise HTTPException(status_code=400, detail="Numéro de téléphone camerounais invalide (+2376XXXXXXXX)")
    return clean[-9:] # Renvoie le format pur à 9 chiffres

# ============================================================
# 🚀 PONT TRANSACTIONNEL : CRÉATION DE COMMANDE / RÉSERVATION
# ============================================================

@router.post("/create", status_code=status.HTTP_201_CREATED)
@limiter.limit("30 per minute")
async def create_order(
    request: Request,
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
):
    """🚀 Enregistre une réservation sur une ligne de production collective"""
    
    # 1. Protection contre les doubles clics réseau (Idempotence)
    if idempotency_key:
        existing_duplicate = db.query(Order).filter(Order.idempotency_key == idempotency_key).first()
        if existing_duplicate:
            logger.info(f"🔄 Requête idempotente capturée: {idempotency_key}")
            return {"status": "success", "order_id": existing_duplicate.id, "duplicate": True}

    # 2. Validation du numéro de téléphone
    clean_customer_phone = validate_cameroon_phone(order_data.phone)

    # 3. Validation de l'existence et de l'état du lot de production (DailyMenu)
    daily_menu = db.query(DailyMenu).filter(DailyMenu.id == order_data.daily_menu_id).first()
    if not daily_menu:
        raise HTTPException(status_code=404, detail="Cette opportunité de menu n'existe pas.")

    # Sécurité d'état de la cuisine
    if daily_menu.status in ["cooking", "completed"]:
        raise HTTPException(status_code=400, detail="Trop tard ! Les cuisines sont closes et le repas est en cuisson.")

    # 4. Calcul de l'impact des portions sur la jauge de production
    portions_to_add = daily_menu.minimum_production if order_data.mode == "pack" else order_data.portions
    
    if daily_menu.max_production and (daily_menu.reserved_portions + portions_to_add) > daily_menu.max_production:
        remaining = daily_menu.max_production - daily_menu.reserved_portions
        raise HTTPException(
            status_code=400, 
            detail=f"Capacité de la marmite saturée. Il ne reste que {remaining} portions disponibles."
        )

    # 5. Instanciation de la commande liée au modèle de production
    new_order = Order(
        daily_menu_id=daily_menu.id,
        product_id=daily_menu.product_id, # Compatibilité historique analytics
        customer_name=order_data.customer_name,
        phone=clean_customer_phone,
        zone=order_data.zone,
        total_amount=order_data.total_amount,
        deposit_amount=order_data.deposit_amount,
        mode=order_data.mode,
        portions=order_data.portions,
        portion_size=order_data.portion_size,
        delivery_date=order_data.delivery_date,
        delivery_time=order_data.delivery_time,
        complement=order_data.complement,
        affiliate_code=order_data.affiliate_code,
        affiliate_payout_phone=order_data.affiliate_payout_phone,
        status="en_attente",
        idempotency_key=idempotency_key
    )
    db.add(new_order)

    # 6. Mise à jour de la jauge collective live de KEMTCHOP
    daily_menu.reserved_portions += portions_to_add

    # 7. Transition d'état automatique du lot (Le premier client déclenche la production)
    if daily_menu.status == "waiting_first_order" and daily_menu.reserved_portions >= daily_menu.minimum_production:
        daily_menu.status = "confirmed"
        daily_menu.launched_at = datetime.utcnow()
        logger.info(f"🔥 Ligne de production CONFIRMÉE pour le plat ID: {daily_menu.product_id}")

    # 8. Distribution des gains d'affiliation (Ambassadeurs KEMTCHOP)
    if order_data.affiliate_code:
        ambassador = db.query(User).filter(
            User.affiliate_code == order_data.affiliate_code, 
            User.is_affiliate == True
        ).first()
        if ambassador:
            commission = order_data.total_amount * 0.15
            ambassador.pending_commissions = (ambassador.pending_commissions or 0) + commission
            logger.info(f"💰 Commission +{commission} FCFA enregistrée pour l'ambassadeur {order_data.affiliate_code}")

    db.commit()
    db.refresh(new_order)

    # 9. Notification Push asynchrone (Engagement client direct)
    if new_order.phone:
        client = db.query(User).filter(User.phone == new_order.phone).first()
        if client and client.expo_push_token:
            body_msg = (
                f"Félicitations ! Tu as initié la production ! Ton menu est à lancer 🚀"
                if daily_menu.status == "waiting_first_order"
                else f"Ta portion de {daily_menu.product.product_name} est réservée pour demain ! 🍳"
            )
            asyncio.create_task(ExpoPushService.send_notification(
                expo_token=client.expo_push_token,
                title="Production KEMTCHOP 🍲",
                body=body_msg,
                data={"orderId": new_order.id, "type": "order_confirmed"}
            ))

    logger.info(f"✅ Réservation #{new_order.id} validée sur le Menu #{daily_menu.id}")
    return {"status": "success", "order_id": new_order.id, "menu_status": daily_menu.status, "duplicate": False}

# ============================================================
# 📋 FLUX DE CONSULTATION ET SUIVI
# ============================================================

@router.get("/my-orders", response_model=List[OrderResponse])
@limiter.limit("60 per minute")
def get_my_orders(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """📋 Historique personnel de l'utilisateur mobile connecté"""
    user_phone = current_user.get("phone")
    if not user_phone:
        raise HTTPException(status_code=403, detail="Identifiant de session corrompu.")
    
    clean_phone = re.sub(r'\D', '', user_phone)[-9:]
    orders = db.query(Order).filter(Order.phone == clean_phone).order_by(Order.created_at.desc()).all()
    return orders

# ============================================================
# ⚙️ UNIVERS ADMINISTRATION CONTROL
# ============================================================

@router.patch("/admin/{order_id}/status")
@limiter.limit("30 per minute")
async def update_order_status(
    request: Request, 
    order_id: int, 
    new_status: str, 
    db: Session = Depends(get_db), 
    current_admin: dict = Depends(check_permission("orders"))
):
    """📦 [ADMIN] Modifie arbitrairement l'état d'une commande (ex: livrée)"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable.")
    
    old_status = order.status
    order.status = new_status
    db.commit()
    logger.info(f"⚙️ Modification manuelle admin de la Commande #{order_id} : {old_status} → {new_status}")
    return {"status": "success", "new_status": order.status}

@router.get("/admin", response_model=List[OrderResponse])
@limiter.limit("60 per minute")
async def get_admin_orders(
    request: Request, 
    db: Session = Depends(get_db), 
    current_admin: dict = Depends(check_permission("orders")), 
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, ge=1, le=500)
):
    """📊 [ADMIN] Flux global de toutes les réservations du réseau (Tri antichronologique)"""
    return db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()