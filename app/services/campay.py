# app/services/campay.py
"""
Service d'intégration Campay pour KemTchop
Paiement Mobile Money (MTN/Orange) avec flux 40% d'acompte
"""

import os
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from httpx import AsyncClient, Timeout
from fastapi import HTTPException, status

logger = logging.getLogger("kemtchop.campay")

# Configuration
CAMPAY_BASE_URL = "https://campay.net/api/v2"
CAMPAY_PUBLIC_KEY = os.getenv("CAMPAY_PUBLIC_KEY")
CAMPAY_PRIVATE_KEY = os.getenv("CAMPAY_PRIVATE_KEY")
CAMPAY_MODE = os.getenv("CAMPAY_MODE", "sandbox")  # "sandbox" ou "production"
CAMPAY_WEBHOOK_SECRET = os.getenv("CAMPAY_WEBHOOK_SECRET")

# Timeout pour les appels API
HTTP_TIMEOUT = Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)


class CampayService:
    """Service pour interagir avec l'API Campay"""
    
    def __init__(self):
        if not CAMPAY_PUBLIC_KEY or not CAMPAY_PRIVATE_KEY:
            logger.error("❌ Campay credentials not configured in .env")
            raise RuntimeError("Campay API keys must be set in environment variables")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Génère les headers d'authentification pour Campay"""
        return {
            "Authorization": f"Token {CAMPAY_PRIVATE_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def create_payment(
        self,
        amount: float,
        description: str,
        reference: str,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Crée une demande de paiement Campay
        
        Args:
            amount: Montant en FCFA (ex: 2000 pour 2000 FCFA)
            description: Description du paiement
            reference: Référence unique de la transaction (order_id)
            phone: Numéro de téléphone du client (optionnel, pour pré-remplir)
            metadata: Données additionnelles à associer
        
        Returns:
            Dict avec payment_url, reference, status, etc.
        """
        async with AsyncClient(timeout=HTTP_TIMEOUT) as client:
            payload = {
                "amount": int(amount),  # Campay attend un entier
                "currency": "XAF",
                "description": description,
                "reference": reference,
                "metadata": metadata or {},
            }
            
            if phone:
                # Format attendu par Campay : 2376XXXXXXXX
                clean_phone = phone.replace("+", "").replace(" ", "")
                if not clean_phone.startswith("237"):
                    clean_phone = f"237{clean_phone}"
                payload["phone_number"] = clean_phone
            
            try:
                response = await client.post(
                    f"{CAMPAY_BASE_URL}/payment/",
                    headers=await self._get_auth_headers(),
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"✅ Paiement Campay créé : {reference} → {result.get('payment_url')}")
                return {
                    "success": True,
                    "payment_url": result.get("payment_url"),
                    "reference": result.get("reference"),
                    "uuid": result.get("uuid"),
                    "status": result.get("status"),  # "PENDING"
                    "amount": result.get("amount"),
                    "currency": result.get("currency"),
                }
                
            except Exception as e:
                logger.error(f"❌ Erreur création paiement Campay : {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Impossible d'initialiser le paiement. Veuillez réessayer."
                )
    
    async def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Vérifie le statut d'un paiement Campay
        
        Args:
            reference: Référence de la transaction
            
        Returns:
            Dict avec status, amount, paid_at, etc.
        """
        async with AsyncClient(timeout=HTTP_TIMEOUT) as client:
            try:
                response = await client.get(
                    f"{CAMPAY_BASE_URL}/payment/{reference}/",
                    headers=await self._get_auth_headers()
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "success": True,
                    "status": result.get("status"),  # "SUCCESS", "PENDING", "FAILED"
                    "amount": result.get("amount"),
                    "currency": result.get("currency"),
                    "paid_at": result.get("paid_at"),
                    "method": result.get("method"),  # "MTN", "ORANGE", "CARD"
                    "phone": result.get("phone_number"),
                }
                
            except Exception as e:
                logger.error(f"❌ Erreur vérification paiement Campay : {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Impossible de vérifier le statut du paiement."
                )
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """
        Vérifie la signature HMAC d'un webhook Campay
        
        Args:
            payload: Corps brut de la requête webhook
            signature: Header 'X-Campay-Signature' reçu
            
        Returns:
            bool: True si la signature est valide
        """
        if not CAMPAY_WEBHOOK_SECRET:
            logger.warning("⚠️ CAMPAY_WEBHOOK_SECRET non défini - vérification webhook désactivée")
            return True  # En dev, on peut accepter sans vérification
        
        expected_signature = hmac.new(
            CAMPAY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


# Instance singleton pour réutilisation
campay_service = CampayService()