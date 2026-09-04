# app/routes/payments.py
# ============================================================
# 💳 ROUTES PAIEMENT & AFFILIÉS - KemTchop API
# ============================================================

import os
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities import Order, User, DailyOffer
from app.enums import OrderStatus, ProductionStatus
from app.auth import check_permission, get_current_user
from app.services.notification_service import NotificationService
from pydantic import BaseModel

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

class SimulatePaymentRequest(BaseModel):
    order_id: str

# ============================================================
# 💳 CAMPAY PAYMENT
# ============================================================
@router.post("/campay/init", response_model=PaymentInitResponse)
@limiter.limit("20 per minute")
async def init_campay_payment(request: Request, payment_request: PaymentInitRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == payment_request.order_id, Order.status.in_(["pending", "en_attente", OrderStatus.PENDING.value])).first()
    if not order: 
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    deposit = round(payment_request.amount * 0.40)
    balance = round(payment_request.amount * 0.60)
    ref = f"KEMTCHOP-{payment_request.order_id}-{deposit}"
    
    try:
        result = await campay_service.create_payment(
            amount=deposit, 
            description=payment_request.description or f"Acompte #{payment_request.order_id}", 
            reference=ref, 
            phone=payment_request.phone, 
            metadata={"order_id": payment_request.order_id, "total": payment_request.amount, "balance": balance}
        )
        if not result.get("success"): 
            raise HTTPException(status_code=500, detail="Échec initialisation paiement")
        
        if hasattr(Order, 'campay_reference'):
            order.campay_reference = ref
        if hasattr(Order, 'deposit_amount'):
            order.deposit_amount = deposit
        db.commit()
        
        logger.info(f"💳 Paiement Campay : {ref} → {deposit} FCFA")
        return PaymentInitResponse(
            success=True, 
            payment_url=result["payment_url"], 
            reference=ref, 
            deposit_amount=deposit, 
            balance_amount=balance, 
            message=f"Veuillez payer {deposit} FCFA"
        )
    except HTTPException: 
        raise
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
        logger.info(f"🔔 Webhook Campay: {data.get('reference')} → {data.get('status')}")
        
        order_id = data.get("external_reference")
        order = None
        
        if not order_id:
            ref = data.get("reference")
            order = db.query(Order).filter(Order.campay_reference == ref).first()
        else:
            order = db.query(Order).filter(Order.id == order_id).first()

        if data.get("status") == "SUCCESS" and order:
            if order.status in [OrderStatus.PENDING.value, "pending", "en_attente"]:
                order.status = OrderStatus.PAID.value
                if hasattr(Order, 'payment_status'):
                    order.payment_status = "acompte_paye"
                if hasattr(Order, 'payment_reference'):
                    order.payment_reference = data.get("reference")

                # 🔥 LOGIQUE DE MACHINE D'ÉTAT KEMTCHOP v3.0 (DailyOffer)
                offer = order.daily_offer
                if offer:
                    offer.reserved_portions += order.portions
                    offer.current_revenue += order.total_amount
                    logger.info(f"📈 Marmite {offer.id} : {offer.reserved_portions}/{offer.minimum_threshold} portions")

                    if offer.status == ProductionStatus.PROPOSED.value:
                        offer.status = ProductionStatus.RESERVATION.value
                        logger.info(f"🟠 Marmite {offer.id} passe en RESERVATION")

                    if offer.status in [ProductionStatus.RESERVATION.value, "reservation"] and offer.is_threshold_reached:
                        offer.status = ProductionStatus.CONFIRMED.value
                        offer.triggered_at = datetime.utcnow()
                        logger.info(f"🚀 SEUIL ATTEINT : Marmite {offer.id} confirmée !")
                        try:
                            # 🔥 Récupérer les tokens des participants pour notification
                            participants = db.query(User.expo_push_token).join(
                                Order, Order.phone == User.phone
                            ).filter(
                                Order.daily_offer_id == offer.id,
                                User.expo_push_token.isnot(None),
                                User.expo_push_token != ""
                            ).distinct().all()

                            tokens = [t[0] for t in participants]

                            await NotificationService.notify_offer_confirmed(
                                str(offer.id),
                                offer.product.name if offer.product else "Plat du jour",
                                tokens
                            )
                        except Exception as e:
                            logger.warning(f"Notification échouée: {e}")

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
        return {
            "order_id": str(order.id), 
            "order_status": order.status, 
            "payment_status": getattr(order, 'payment_status', None), 
            "campay_reference": reference
        }
    return {"status": "not_found"}

# ============================================================
# 🧪 SIMULATION DE PAIEMENT (UNIQUEMENT POUR DÉVELOPPEMENT)
# ============================================================
@router.post("/simulate-success")
async def simulate_payment_success(
    request_data: SimulatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Simule un webhook de paiement réussi pour les tests"""
    order = db.query(Order).filter(Order.id == request_data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    # Marquer la commande comme payée
    order.status = OrderStatus.PAID.value
    if hasattr(Order, 'payment_status'):
        order.payment_status = "acompte_paye"
    
    # Mettre à jour l'offre liée (DailyOffer)
    offer = db.query(DailyOffer).filter(DailyOffer.id == order.daily_offer_id).first()
    if offer:
        offer.reserved_portions += order.portions
        offer.current_revenue += order.total_amount
        
        # 🔥 LOGIQUE DE DÉCLENCHEMENT AUTOMATIQUE
        if offer.reserved_portions >= offer.minimum_threshold and offer.status in [ProductionStatus.PROPOSED.value, "proposed"]:
            offer.status = ProductionStatus.CONFIRMED.value
            offer.triggered_at = datetime.utcnow()
            logger.info(f"🚀 [SIMULATION] SEUIL ATTEINT ! {offer.product.name if offer.product else 'Plat'} passe en MENU DU JOUR.")
    
    db.commit()
    logger.info(f"✅ [SIMULATION] Paiement réussi pour la commande {order.id}")
    
    return {
        "status": "success",
        "message": "Paiement simulé avec succès. Seuil vérifié."
    }

# ============================================================
# 🤝 AFFILIÉS & COMMISSIONS
# ============================================================
@router.get("/ambassador/{affiliate_code}")
@limiter.limit("60 per minute")
async def get_ambassador_sales(request: Request, affiliate_code: str, db: Session = Depends(get_db)):
    ambassador = db.query(User).filter(User.affiliate_code == affiliate_code, User.is_affiliate == True).first()
    if not ambassador: 
        raise HTTPException(status_code=404, detail="Affilié non trouvé")
    
    orders = db.query(Order).filter(
        Order.affiliate_code == affiliate_code,
        Order.status == OrderStatus.DELIVERED.value,
        Order.commission_paid == False
    ).order_by(Order.created_at.desc()).all()

    total = sum(float(o.total_amount or 0) for o in orders)
    
    return {
        "affiliate_code": affiliate_code, 
        "ambassador_name": ambassador.customer_name,
        "total_sales": total, 
        "pending_commission": round(total * 0.15, 2), 
        "orders_count": len(orders),
        "orders": [{
            "id": str(o.id), 
            "product_name": o.product_name, 
            "customer_name": o.customer_name, 
            "total_amount": float(o.total_amount), 
            "commission": round(float(o.total_amount) * 0.15, 2), 
            "created_at": o.created_at.isoformat() if o.created_at else None, 
            "status": o.status
        } for o in orders]
    }