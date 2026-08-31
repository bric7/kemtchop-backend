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
from app.entities import Order, User, DailyOffer
from app.enums import OrderStatus, ProductionStatus
from app.auth import check_permission
from app.services.notification_service import NotificationService

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
router = APIRouter(prefix="/payments", tags=["Payments"])
logger = logging.getLogger("kemtchop")
limiter = Limiter(key_func=get_remote_address)

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
from pydantic import BaseModel

class PaymentInitRequest(BaseModel):
    order_id: str
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
    order = db.query(Order).filter(Order.id == payment_request.order_id, Order.status.in_(["pending", "en_attente"])).first()
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
        
    try:
        # data["external_reference"] contient l'ID de la commande envoyé lors de init
        order_id = data.get("external_reference")

        # Fallback sur le parsing du metadata ou de la référence si external_reference est vide
        if not order_id:
            # Campay envoie souvent l'external_reference, mais parfois il faut le retrouver dans le metadata
            # ou via notre propre système de tracking de référence
            ref = data.get("reference")
            order = db.query(Order).filter(Order.campay_reference == ref).first()
        else:
            order = db.query(Order).filter(Order.id == order_id).first()

        if data["status"] == "SUCCESS" and order:
            if order.status == OrderStatus.PENDING.value:
                order.status = OrderStatus.PAID.value

                if hasattr(Order, 'payment_reference'):
                    order.payment_reference = data["reference"]

                # 🔥 LOGIQUE DE MACHINE D'ÉTAT KEMTCHOP v3.0 (DailyOffer)
                offer = order.daily_offer
                if offer:
                    # 1. Incrémenter les portions réservées PAYÉES
                    offer.reserved_portions += order.portions
                    offer.current_revenue += order.total_amount

                    logger.info(f"📈 Marmite {offer.id} : {offer.reserved_portions}/{offer.minimum_threshold} portions")

                    # 2. Transition PROPOSED -> RESERVATION (1ère commande)
                    if offer.status == ProductionStatus.PROPOSED.value:
                        offer.status = ProductionStatus.RESERVATION.value
                        logger.info(f"🟠 Marmite {offer.id} passe en RESERVATION")

                    # 3. Transition -> CONFIRMED (Seuil atteint)
                    if offer.status == ProductionStatus.RESERVATION.value and offer.is_threshold_reached:
                        offer.status = ProductionStatus.CONFIRMED.value
                        from datetime import datetime
                        offer.triggered_at = datetime.utcnow()
                        logger.info(f"🚀 SEUIL ATTEINT : Marmite {offer.id} confirmée !")

                        # 🔔 Notification Admin & Clients
                        await NotificationService.notify_offer_confirmed(
                            str(offer.id),
                            offer.product.name if offer.product else "Plat du jour"
                        )

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
    
    # On ne compte que les ventes dont le statut de commande est 'delivered' ou 'ready' etc (tout ce qui est payé/fini)
    # Dans le nouveau modèle, 'delivered' semble être le statut final pour le client.
    # On va utiliser OrderStatus.DELIVERED si disponible, sinon "delivered"
    from app.enums import OrderStatus

    orders = db.query(Order).filter(
        Order.affiliate_code == affiliate_code,
        Order.status == OrderStatus.DELIVERED.value,
        Order.commission_paid == False
    ).order_by(Order.created_at.desc()).all()

    total = sum(float(o.total_amount or 0) for o in orders)
    
    return {
        "affiliate_code": affiliate_code, "ambassador_name": ambassador.customer_name,
        "total_sales": total, "pending_commission": round(total * 0.15, 2), "orders_count": len(orders),
        "orders": [{"id": str(o.id), "product_name": o.product_name, "customer_name": o.customer_name, "total_amount": float(o.total_amount), "commission": round(float(o.total_amount) * 0.15, 2), "created_at": o.created_at.isoformat() if o.created_at else None, "status": o.status} for o in orders]
    }
