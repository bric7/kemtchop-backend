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

from app.database import get_db
from app.models import Reel, Order, User, DeliverySettings, UserEvent
from app.auth import check_permission
from app.services.cloudinary_service import CloudinaryService
from app.services.expo_push import ExpoPushService

# ============================================================
# 🔧 CONFIG
# ============================================================
router = APIRouter()
logger = logging.getLogger("kemtchop")
limiter = Limiter(key_func=get_remote_address)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "https://tchopiol-production.up.railway.app/videos")

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

@router.post("/admin/upload-content")
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
        logger.info(f"🔍 [Upload Debug] Cloudinary config: cloud_name={os.getenv('CLOUDINARY_CLOUD_NAME')}, secure={cloudinary.config().secure}")
        
        image_result = await CloudinaryService.upload_image(image.file, folder="kemtchop/products")
        logger.info(f"🔍 [Upload Debug] Résultat upload image: success={image_result.get('success')}, url={image_result.get('url')}")
        
        if not image_result["success"]:
            logger.error(f"❌ Échec upload image: {image_result.get('error')}")
            raise HTTPException(status_code=500, detail=f"Erreur upload image: {image_result.get('error')}")
        
        image_url = image_result["url"]
        logger.info(f"✅ Image URL finale: {image_url}")
        
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
        
        logger.info(f"✅ Produit créé avec succès: {product_name} (ID: {new_reel.id})")
        return {"status": "success", "message": f"Menu {product_name} configuré", "id": new_reel.id, "image_url": image_url, "video_url": video_url}
        
    except Exception as e:
        logger.error(f"❌ Erreur upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/products")
@limiter.limit("100 per minute")
async def get_admin_products(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_products"))):
    return db.query(Reel).order_by(Reel.created_at.desc()).all()

@router.delete("/admin/products/{product_id}")
@limiter.limit("10 per minute")
async def delete_product(request: Request, product_id: int, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_products"))):
    p = db.query(Reel).filter(Reel.id == product_id).first()
    if not p: raise HTTPException(status_code=404, detail="Plat non trouvé")
    db.delete(p)
    db.commit()
    logger.info(f"🗑️ Plat supprimé : #{product_id}")
    return {"status": "success"}

@router.put("/admin/products/{product_id}/set-hero")
@limiter.limit("10 per minute")
async def set_hero_product(request: Request, product_id: int, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_products"))):
    p = db.query(Reel).filter(Reel.id == product_id).first()
    if not p: raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    if hasattr(Reel, 'is_hero'):
        db.query(Reel).update({Reel.is_hero: False})
        p.is_hero = True
        db.commit()
        logger.info(f"⭐ Produit phare défini : {p.product_name}")
        return {"message": f"{p.product_name} est maintenant le produit phare !"}
    else:
        logger.warning(f"⚠️ is_hero non supporté sur Reel - action ignorée pour #{product_id}")
        return {"message": f"{p.product_name} - is_hero non disponible", "warning": "Ajoute 'is_hero' au modèle Reel pour activer cette fonctionnalité"}

# ============================================================
# ⚙️ PARAMÈTRES & CONFIGURATION
# ============================================================
@router.get("/settings/delivery-zones")
@limiter.limit("60 per minute")
def get_delivery_settings(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_settings"))):
    settings = db.query(DeliverySettings).first()
    if not settings: return {"zones": ["Bastos", "Akwa", "Bonapriso", "Odza"], "price": 1000}
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
    logger.info(f"⚙️ Zones livraison mises à jour")
    return {"status": "success", "message": "Paramètres enregistrés"}

# ============================================================
# 📊 ANALYTICS & STATISTIQUES
# ============================================================
@router.get("/stats")
@limiter.limit("60 per minute")
async def get_admin_stats(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(check_permission("dashboard"))):
    try:
        total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
        total_orders = db.query(Order).count()
        total_products = db.query(Reel).filter(Reel.is_available == True).count()
        affiliate_sum = db.query(func.sum(Order.total_amount)).filter(Order.affiliate_code.isnot(None), Order.affiliate_code != "").scalar() or 0
        total_commissions = float(affiliate_sum) * 0.15
        top = db.query(Order.product_name, func.count(Order.product_name).label('count')).filter(Order.status == "termine").group_by(Order.product_name).order_by(func.count(Order.product_name).desc()).first()
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
    orders = db.query(Order).filter(Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.commission_paid == False, Order.status == "termine").all()
    payouts = []
    for o in orders:
        payouts.append({
            "order_id": o.id, "affiliate_code": o.affiliate_code, "amount": round(o.total_amount * 0.15, 2),
            "payout_phone": o.affiliate_payout_phone, "customer": o.customer_name,
            "order_date": o.created_at.isoformat() if o.created_at else None
        })
    return payouts

@router.get("/payouts-summary")
@limiter.limit("30 per minute")
def get_payouts_summary(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    summary = db.query(Order.affiliate_code, Order.affiliate_payout_phone, func.sum(Order.total_amount * 0.15).label("total"), func.count(Order.id).label("count")).filter(Order.status == "termine", Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.commission_paid == False).group_by(Order.affiliate_code, Order.affiliate_payout_phone).all()
    return [{"affiliate_code": r.affiliate_code, "payout_phone": r.affiliate_payout_phone, "total_to_pay": round(float(r.total), 2), "order_count": r.count} for r in summary]

# --- Analytics Tracking ---
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
        logger.info(f"📊 Event tracked: {event.phone} → {event.event_type}")
        return {"status": "success", "message": "Événement enregistré"}
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur tracking : {e}")
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

@router.get("/analytics/video-interest", response_model=List[CampaignTarget])
@limiter.limit("30 per minute")
async def get_video_interested_users(request: Request, video_id: Optional[int] = Query(None), hours: int = Query(72, ge=1, le=168), db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_affiliates"))):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    viewed = db.query(UserEvent.phone, func.max(UserEvent.created_at).label('last')).filter(UserEvent.event_type == 'video_view', UserEvent.created_at >= cutoff)
    if video_id: viewed = viewed.filter(UserEvent.video_id == video_id)
    viewed = viewed.group_by(UserEvent.phone).all()
    
    targets = []
    for row in viewed:
        converted = db.query(UserEvent).filter(UserEvent.phone == row.phone, UserEvent.event_type == 'order_completed', UserEvent.created_at > row.last).first()
        if not converted:
            user = db.query(User).filter(User.phone == row.phone).first()
            targets.append(CampaignTarget(phone=row.phone, customer_name=user.customer_name if user else "Inconnu", last_event='video_view', last_event_date=row.last, product_interest="Vidéo KemTchop", cart_value=None, total_events=1))
        if len(targets) >= 100: break
    return targets

@router.post("/notifications/send")
@limiter.limit("5 per minute")
async def send_push_campaign(request: Request, campaign: PushCampaignRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    query = db.query(User.expo_push_token).filter(User.expo_push_token.isnot(None), User.expo_push_token != "")
    if campaign.target == "affiliates": query = query.filter(User.is_affiliate == True)
    elif campaign.target.startswith("segment:VIP"):
        query = query.join(Order).filter(Order.status == "termine").having(func.sum(Order.total_amount) >= 50000)
    
    tokens = [t[0] for t in query.distinct().all() if t[0]]
    if not tokens: return {"status": "warning", "message": "Aucun token valide"}
    
    result = await ExpoPushService.send_bulk_notifications(tokens=tokens, title=campaign.title, body=campaign.body, data=campaign.data)
    logger.info(f"📢 Campagne push: {result['success']} envoyés, {result['failed']} échecs")
    return {"status": "success", "sent": result["success"], "failed": result["failed"], "errors": result["errors"][:10]}