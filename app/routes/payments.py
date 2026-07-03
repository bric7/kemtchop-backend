# app/routes/payments.py
# ============================================================
# 💳 ROUTES PAIEMENT & AFFILIÉS - KemTchop API
# ============================================================

import os
import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Query
from slowapi import Limiter
from slowapi.util import get_remote_address

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Order, User
from app.auth import check_permission

# ✅ Campay: fallback sécurisé si le service n'existe pas
try:
    from app.services.campay import campay_service
except ImportError:
    class MockCampayService:
        @staticmethod
        async def create_payment(**kwargs):
            logging.warning("⚠️ Campay non configuré - mode simulation")
            return {"success": True, "payment_url": "https://campay.net/mock", "reference": "MOCK-REF"}
        @staticmethod
        def verify_webhook_signature(body: bytes, signature: str) -> bool:
            is_prod = os.getenv("EXPO_PUBLIC_ENV") == "production"
            return not is_prod
        @staticmethod
        def parse_webhook_payload(payload: dict) -> dict:
            return payload
    campay_service = MockCampayService()

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

class PaymentInitRequest(BaseModel):
    order_id: int
    amount: float
    phone: str
    description: Optional[str] = "Acompte KemTchop"

class PaymentInitResponse(BaseModel):
    success: bool
    payment_url: str
    reference: str
    deposit_amount: float
    balance_amount: float
    message: str

# ============================================================
# 💳 CAMPAY PAYMENT
# ============================================================
@router.post("/campay/init", response_model=PaymentInitResponse)
@limiter.limit("20 per minute")
async def init_campay_payment(request: Request, payment_request: PaymentInitRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == payment_request.order_id, Order.status == "en_attente").first()
    if not order: raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    deposit = round(payment_request.amount * 0.40)
    balance = round(payment_request.amount * 0.60)
    ref = f"KEMTCHOP-{payment_request.order_id}-{deposit}"
    
    try:
        result = await campay_service.create_payment(amount=deposit, description=payment_request.description or f"Acompte #{payment_request.order_id}", reference=ref, phone=payment_request.phone, metadata={"order_id": payment_request.order_id, "total": payment_request.amount, "balance": balance})
        if not result.get("success"): raise HTTPException(status_code=500, detail="Échec initialisation paiement")
        
        if hasattr(Order, 'campay_reference'):
            order.campay_reference = ref
        if hasattr(Order, 'deposit_amount'):
            order.deposit_amount = deposit
        db.commit()
        
        logger.info(f"💳 Paiement Campay : {ref} → {deposit} FCFA")
        return PaymentInitResponse(success=True, payment_url=result["payment_url"], reference=ref, deposit_amount=deposit, balance_amount=balance, message=f"Veuillez payer {deposit} FCFA")
    except HTTPException: raise
    except Exception as e:
        logger.error(f"❌ Erreur init Campay : {e}")
        raise HTTPException(status_code=500, detail="Erreur initialisation paiement")

@router.post("/campay/webhook")
@limiter.limit("100 per minute")
async def campay_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.body()
        signature = request.headers.get("X-Campay-Signature", "")
        
        is_prod = os.getenv("EXPO_PUBLIC_ENV") == "production"
        if is_prod and not campay_service.verify_webhook_signature(body, signature):
            logger.error("🚫 Webhook Campay rejeté : signature invalide")
            raise HTTPException(status_code=401, detail="Signature invalide")
        
        data = campay_service.parse_webhook_payload(await request.json())
        logger.info(f"🔔 Webhook Campay: {data['reference']} → {data['status']}")
        
        if data["status"] == "SUCCESS" and data["external_reference"]:
            order = db.query(Order).filter(Order.id == data["external_reference"]).first()
            if order:
                order.status = "acompte_paye"
                if hasattr(Order, 'payment_reference'):
                    order.payment_reference = data["reference"]
                db.commit()
                logger.info(f"✅ Commande #{order.id} marquée payée")
        return {"status": "received"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur webhook : {e}")
        return {"status": "error"}

@router.get("/campay/status/{reference}")
@limiter.limit("60 per minute")
async def get_campay_status(request: Request, reference: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.campay_reference == reference).first()
    if order:
        return {"order_id": order.id, "order_status": order.status, "payment_status": getattr(order, 'payment_status', None), "campay_reference": reference}
    return {"status": "not_found"}

# ============================================================
# 🤝 AFFILIÉS & COMMISSIONS
# ============================================================
@router.get("/ambassador/{affiliate_code}")
@limiter.limit("60 per minute")
async def get_ambassador_sales(request: Request, affiliate_code: str, db: Session = Depends(get_db)):
    ambassador = db.query(User).filter(User.affiliate_code == affiliate_code, User.is_affiliate == True).first()
    if not ambassador: raise HTTPException(status_code=404, detail="Affilié non trouvé")
    
    orders = db.query(Order).filter(Order.affiliate_code == affiliate_code, Order.status == "termine").order_by(Order.created_at.desc()).all()
    total = sum(float(o.total_amount or 0) for o in orders)
    
    return {
        "affiliate_code": affiliate_code, "ambassador_name": ambassador.customer_name,
        "total_sales": total, "pending_commission": round(total * 0.15, 2), "orders_count": len(orders),
        "orders": [{"id": o.id, "product_name": o.product_name, "customer_name": o.customer_name, "total_amount": float(o.total_amount), "commission": round(float(o.total_amount) * 0.15, 2), "created_at": o.created_at.isoformat() if o.created_at else None, "status": o.status} for o in orders]
    }