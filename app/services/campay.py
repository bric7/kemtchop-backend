# app/services/campay.py
"""
Service Campay simplifié pour KemTchop (mode widget frontend)
Le paiement est géré par le widget JS, le backend reçoit juste les webhooks
"""

import os
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request

logger = logging.getLogger("kemtchop.campay")

CAMPAY_WEBHOOK_SECRET = os.getenv("CAMPAY_WEBHOOK_SECRET")

class CampayService:
    """Service minimaliste pour webhooks Campay"""
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """Vérifie la signature HMAC d'un webhook Campay"""
        if not CAMPAY_WEBHOOK_SECRET:
            logger.warning("⚠️ CAMPAY_WEBHOOK_SECRET non défini - mode dev")
            return True
        
        try:
            expected = hmac.new(
                CAMPAY_WEBHOOK_SECRET.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"❌ Erreur signature webhook: {e}")
            return False
    
    @staticmethod
    def parse_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse le payload du webhook Campay"""
        return {
            "reference": payload.get("reference"),
            "status": payload.get("status"),  # SUCCESS, PENDING, FAILED
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "paid_at": payload.get("paid_at"),
            "method": payload.get("method"),  # MTN, ORANGE, CARD
            "phone": payload.get("phone_number"),
            "external_reference": payload.get("external_reference"),  # Ton order_id
        }

campay_service = CampayService()