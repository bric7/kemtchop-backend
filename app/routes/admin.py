# app/routes/admin.py
# ============================================================
# ⚙️ ROUTES ADMIN - KemTchop API
# ============================================================

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks, File, Form, UploadFile, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.config import settings
from app.database import get_db
from app.entities import Reel, Order, User, DeliverySettings, UserEvent
from app.auth import check_permission
from app.services.cloudinary_service import CloudinaryService
from app.services.expo_push import ExpoPushService
from app.utils.timezone import get_business_datetime

# ============================================================
# 🔧 CONFIG
# ============================================================
router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger("kemtchop")
limiter = Limiter(key_func=get_remote_address)

BASE_URL = settings.BASE_URL
MEDIA_BASE_URL = settings.MEDIA_BASE_URL

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
from pydantic import BaseModel, Field

class ReelResponse(BaseModel):
    id: int
    title: str
    video_url: Optional[str] = None
    image_url: str
    product_name: str
    price: float
    category: Optional[str] = "Tout"
    is_available: Optional[bool] = True
    complements: Optional[str] = None
    class Config:
        from_attributes = True

class DeliverySettingsUpdate(BaseModel):
    zones: List[str]
    price: int

class AnalyticsEvent(BaseModel):
    phone: str = Field(..., min_length=9, max_length=15)
    event_type: str = Field(..., pattern="^(video_view|product_view|add_to_cart|checkout_start|checkout_abandon|order_completed|affiliate_click|search)$")
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    video_id: Optional[int] = None
    cart_value: Optional[float] = None
    affiliate_code: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = {}

class CampaignTarget(BaseModel):
    phone: str
    customer_name: Optional[str] = None
    last_event: str
    last_event_date: datetime
    product_interest: Optional[str] = None
    cart_value: Optional[float] = None
    total_events: int
    class Config:
        from_attributes = True

class PushCampaignRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    target: str = Field(default="all")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sound: Optional[str] = Field(default="default")
    class Config:
        from_attributes = True

class AdminUserResponse(BaseModel):
    id: str
    phone: str
    customer_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    permissions: Optional[str] = None
    affiliate_code: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class UpdateUserRoleRequest(BaseModel):
    role: str
    permissions: Optional[str] = None

# ============================================================
# 🎬 PRODUITS / REELS
# ============================================================
@router.get("/reels/", response_model=list[ReelResponse])
@limiter.limit("100 per minute")
def get_reels(request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), category: Optional[str] = Query(None), available_only: bool = Query(False)):
    query = db.query(Reel)
    if category and category != "Tout": query = query.filter(Reel.category == category)
    if available_only: query = query.filter(Reel.is_available == True)
    reels = query.order_by(Reel.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for r in reels:
        img = r.image_url.split('/')[-1] if r.image_url else None
        vid = r.video_url.split('/')[-1] if r.video_url else None
        result.append({
            "id": r.id, "title": r.title, "product_name": r.product_name, "category": getattr(r, 'category', "Tout"),
            "is_available": getattr(r, 'is_available', True), "price": r.price,
            "price_solo": getattr(r, 'price_solo', r.price), "price_duo": getattr(r, 'price_duo', r.price * 1.8),
            "price_family": getattr(r, 'price_family', r.price * 3), "family_size": getattr(r, 'family_size', 3),
            "complements": r.complements,
            "image_url": f"{MEDIA_BASE_URL}/videos/{img}" if img else "",
            "thumbnail": f"{MEDIA_BASE_URL}/videos/{img}" if img else "",
            "video_url": f"{MEDIA_BASE_URL}/videos/{vid}" if vid else None
        })
    return result

@router.post("/upload-content")
@limiter.limit("5 per minute")
async def upload_content(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    product_name: str = Form(...),
    category: str = Form("Grillades"),
    is_available: str = Form("true"),
    price_solo: float = Form(...),
    price_duo: float = Form(...),
    price_family: float = Form(...),
    family_size: int = Form(3),
    complements: str = Form(None),
    image: UploadFile = File(...),
    video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_products"))
):
    try:
        logger.info(f"🔍 [Upload Debug] Cloudinary config: cloud_name={os.getenv('CLOUDINARY_CLOUD_NAME')}")
        
        image_result = await CloudinaryService.upload_image(image.file, folder="kemtchop/products")
        if not image_result["success"]:
            raise HTTPException(status_code=500, detail=f"Erreur upload image: {image_result.get('error')}")
        
        image_url = image_result["url"]
        video_url = None
        if video and video.filename:
            video_result = await CloudinaryService.upload_video(video.file, folder="kemtchop/videos")
            if video_result["success"]:
                video_url = video_result["url"]
        
        available_bool = str(is_available).lower() in ["true", "1", "yes", "on"]
        new_reel = Reel(
            title=title, product_name=product_name, category=category, is_available=available_bool,
            price=price_solo, price_solo=price_solo, price_duo=price_duo, price_family=price_family,
            family_size=family_size, complements=complements, image_url=image_url, video_url=video_url,
        )
        
        db.add(new_reel)
        db.commit()
        db.refresh(new_reel)
        
        return {"status": "success", "message": f"Menu {product_name} configuré", "id": new_reel.id, "image_url": image_url, "video_url": video_url}
    except Exception as e:
        logger.error(f"❌ Erreur upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products")
@limiter.limit("100 per minute")
async def get_admin_products(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_products"))):
    return db.query(Reel).order_by(Reel.created_at.desc()).all()

@router.delete("/products/{product_id}")
@limiter.limit("10 per minute")
async def delete_product(request: Request, product_id: int, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_products"))):
    p = db.query(Reel).filter(Reel.id == product_id).first()
    if not p: raise HTTPException(status_code=404, detail="Plat non trouvé")
    db.delete(p)
    db.commit()
    return {"status": "success"}

@router.put("/products/{product_id}/set-hero")
@limiter.limit("10 per minute")
async def set_hero_product(request: Request, product_id: int, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_products"))):
    p = db.query(Reel).filter(Reel.id == product_id).first()
    if not p: raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    if hasattr(Reel, 'is_hero'):
        db.query(Reel).update({Reel.is_hero: False})
        p.is_hero = True
        db.commit()
        return {"message": f"{p.product_name} est maintenant le produit phare !"}
    return {"message": "is_hero non disponible sur ce modèle"}

# ============================================================
# ⚙️ PARAMÈTRES & CONFIGURATION
# ============================================================
@router.get("/settings/delivery-zones")
@limiter.limit("60 per minute")
def get_delivery_settings(request: Request, db: Session = Depends(get_db)):
    settings = db.query(DeliverySettings).first()
    if not settings:
        return {"zones": ["Bastos", "Akwa", "Bonapriso", "Odza"], "price": 1000}
    return {"zones": settings.zones, "price": settings.base_price}

@router.post("/settings/update-zones")
@limiter.limit("10 per minute")
async def update_delivery_zones(request: Request, data: DeliverySettingsUpdate, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_settings"))):
    settings = db.query(DeliverySettings).first()
    if settings:
        settings.zones, settings.base_price = data.zones, data.price
    else:
        settings = DeliverySettings(zones=data.zones, base_price=data.price)
        db.add(settings)
    db.commit()
    return {"status": "success", "message": "Paramètres enregistrés"}

# ============================================================
# 📊 ANALYTICS & STATISTIQUES
# ============================================================
@router.get("/stats")
@limiter.limit("60 per minute")
async def get_admin_stats(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(check_permission("dashboard"))):
    try:
        from app.enums import OrderStatus
        total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
        total_orders = db.query(Order).count()
        total_products = db.query(Reel).filter(Reel.is_available == True).count()
        affiliate_sum = db.query(func.sum(Order.total_amount)).filter(Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.status == OrderStatus.DELIVERED.value).scalar() or 0
        total_commissions = float(affiliate_sum) * .15
        top = db.query(Order.product_name, func.count(Order.product_name).label('count')).filter(Order.status == OrderStatus.DELIVERED.value).group_by(Order.product_name).order_by(func.count(Order.product_name).desc()).first()
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = db.query(Order).filter(Order.created_at >= week_ago).count()
        return {
            "revenue": float(total_revenue), "orders": int(total_orders), "products": int(total_products),
            "top_product": top[0] if top and top[0] else "Aucun",
            "commissions_pending": float(total_commissions), "recent_orders_7d": int(recent)
        }
    except Exception as e:
        logger.error(f"❌ CRASH STATS : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur calcul stats")

@router.get("/payouts/pending")
@limiter.limit("30 per minute")
async def get_pending_payouts(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    from app.enums import OrderStatus
    orders = db.query(Order).filter(Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.commission_paid == False, Order.status == OrderStatus.DELIVERED.value).all()
    payouts = []
    for o in orders:
        payouts.append({
            "order_id": str(o.id), "affiliate_code": o.affiliate_code, "amount": round(o.total_amount * 0.15, 2),
            "payout_phone": o.affiliate_payout_phone, "customer": o.customer_name,
            "order_date": o.created_at.isoformat() if o.created_at else None
        })
    return payouts

@router.get("/payouts-summary")
@limiter.limit("30 per minute")
def get_payouts_summary(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    from app.enums import OrderStatus
    summary = db.query(Order.affiliate_code, Order.affiliate_payout_phone, func.sum(Order.total_amount * 0.15).label("total"), func.count(Order.id).label("count")).filter(Order.status == OrderStatus.DELIVERED.value, Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.commission_paid == False).group_by(Order.affiliate_code, Order.affiliate_payout_phone).all()
    return [{"affiliate_code": r.affiliate_code, "payout_phone": r.affiliate_payout_phone, "total_to_pay": round(float(r.total), 2), "order_count": r.count} for r in summary]

@router.post("/analytics/track")
@limiter.limit("100 per minute")
async def track_user_event(request: Request, event: AnalyticsEvent, db: Session = Depends(get_db)):
    try:
        db_event = UserEvent(
            phone=event.phone, event_type=event.event_type, product_id=event.product_id,
            product_name=event.product_name, video_id=event.video_id, cart_value=event.cart_value,
            affiliate_code=event.affiliate_code, event_metadata=event.event_metadata or {}
        )
        db.add(db_event)
        db.commit()
        return {"status": "success", "message": "Événement enregistré"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erreur enregistrement")

@router.get("/analytics/abandoned-carts", response_model=List[CampaignTarget])
@limiter.limit("30 per minute")
async def get_abandoned_carts(request: Request, hours: int = Query(48, ge=1, le=168), min_cart_value: float = Query(1000, ge=0), db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    abandonments = db.query(UserEvent).filter(and_(UserEvent.event_type == 'checkout_abandon', UserEvent.created_at >= cutoff, UserEvent.cart_value.isnot(None), UserEvent.cart_value >= min_cart_value)).order_by(UserEvent.created_at.desc()).all()
    
    targets, seen = [], set()
    for ev in abandonments:
        if ev.phone in seen: continue
        has_completed = db.query(UserEvent).filter(and_(UserEvent.phone == ev.phone, UserEvent.event_type == 'order_completed', UserEvent.created_at > ev.created_at)).first()
        if not has_completed:
            product = ev.event_metadata.get('last_product') if isinstance(ev.event_metadata, dict) else ev.product_name
            user = db.query(User).filter(User.phone == ev.phone).first()
            targets.append(CampaignTarget(phone=ev.phone, customer_name=user.customer_name if user else "Inconnu", last_event='checkout_abandon', last_event_date=ev.created_at, product_interest=product, cart_value=float(ev.cart_value) if ev.cart_value else 0, total_events=1))
            seen.add(ev.phone)
        if len(targets) >= 100: break
    return targets

@router.post("/notifications/send")
@limiter.limit("5 per minute")
async def send_push_campaign(request: Request, campaign: PushCampaignRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    from app.enums import OrderStatus
    query = db.query(User.expo_push_token).filter(User.expo_push_token.isnot(None), User.expo_push_token != "")
    if campaign.target == "affiliates": query = query.filter(User.is_affiliate == True)
    
    tokens = [t[0] for t in query.distinct().all() if t[0]]
    if not tokens: return {"status": "warning", "message": "Aucun token valide"}
    
    result = await ExpoPushService.send_bulk_notifications(tokens=tokens, title=campaign.title, body=campaign.body, data=campaign.data)
    return {"status": "success", "sent": result.get("success", 0), "failed": result.get("failed", 0)}

# ============================================================
# 📦 GESTION DES COMMANDES
# ============================================================
@router.get("/orders")
@limiter.limit("50 per minute")
async def get_admin_orders(request: Request, status_filter: Optional[str] = Query(None, alias="status"), db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("dashboard"))):
    query = db.query(Order)
    if status_filter:
        query = query.filter(Order.status == status_filter)

    orders = query.order_by(Order.created_at.desc()).all()
    result = []
    for o in orders:
        order_dict = {
            "id": str(o.id), "customer_name": o.customer_name, "phone": o.phone, "product_name": o.product_name,
            "total_amount": o.total_amount, "portions": o.portions, "status": o.status, "zone": o.zone,
            "delivery_date": o.delivery_date, "delivery_time": o.delivery_time,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "affiliate_code": o.affiliate_code, "commission_paid": o.commission_paid, "daily_offer": None
        }
        if o.daily_offer:
            order_dict["daily_offer"] = {
                "id": str(o.daily_offer.id), "status": o.daily_offer.status,
                "reserved_portions": o.daily_offer.reserved_portions, "minimum_threshold": o.daily_offer.minimum_threshold,
                "product": {"name": o.daily_offer.product.name} if o.daily_offer.product else None
            }
        result.append(order_dict)
    return result

@router.patch("/orders/{order_id}/status")
@limiter.limit("20 per minute")
async def update_order_status(request: Request, order_id: str, new_status: str = Query(...), db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("dashboard"))):
    from app.enums import OrderStatus
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Commande non trouvée")
    try:
        order.status = OrderStatus(new_status).value
        db.commit()
        return {"status": "success", "new_status": order.status}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Statut invalide: {new_status}")

@router.patch("/orders/{order_id}/pay-commission")
@limiter.limit("10 per minute")
async def mark_commission_paid(request: Request, order_id: str, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Commande non trouvée")
    if not order.affiliate_code: raise HTTPException(status_code=400, detail="Pas d'affilié")
    if order.commission_paid: return {"status": "success", "message": "Déjà payée"}
    
    order.commission_paid = True
    db.commit()
    return {"status": "success", "message": "Commission validée"}


# ============================================================
# 👥 GESTION DES UTILISATEURS (NOUVEAU - CORRIGE LES 404)
# ============================================================

@router.get("/users", response_model=List[AdminUserResponse])
@limiter.limit("50 per minute")
def get_all_users(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_users")),
    role: Optional[str] = Query(None, description="Filtrer par rôle (ex: customer, admin)"),
    skip: int = 0,
    limit: int = 100
):
    """Admin : Récupère la liste des utilisateurs"""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return users


@router.get("/users/{user_id}", response_model=AdminUserResponse)
@limiter.limit("50 per minute")
def get_user_detail(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_users"))
):
    """Admin : Détail d'un utilisateur"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


@router.patch("/users/{user_id}/role")
@limiter.limit("10 per minute")
def update_user_role(
    request: Request,
    user_id: str,
    payload: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_users"))
):
    """Admin : Modifie le rôle d'un utilisateur"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Sécurité : empêcher l'admin de se rétrograder lui-même
    if user.phone == current_admin.get("phone") and payload.role != "admin":
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre rôle")
    
    user.role = payload.role
    if payload.permissions is not None:
        user.permissions = payload.permissions
    user.updated_at = get_business_datetime().replace(tzinfo=None)
    
    db.commit()
    return {"status": "success", "message": f"Rôle mis à jour vers {payload.role}"}


@router.delete("/users/{user_id}")
@limiter.limit("10 per minute")
def deactivate_user(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_users"))
):
    """Admin : Désactive un utilisateur (soft delete)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if user.phone == current_admin.get("phone"):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")
    
    user.is_active = False
    user.updated_at = get_business_datetime().replace(tzinfo=None)
    db.commit()
    
    return {"status": "success", "message": "Utilisateur désactivé"}


@router.get("/users/stats/summary")
@limiter.limit("30 per minute")
def get_users_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_users"))
):
    """Admin : Statistiques sur les utilisateurs"""
    return {
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "admins": db.query(User).filter(User.role == "admin").count(),
        "managers": db.query(User).filter(User.role == "manager").count(),
        "customers": db.query(User).filter(User.role == "customer").count(),
    }