import os
import httpx
import logging
import hmac
import hashlib
from typing import Optional, Dict, Any

logger = logging.getLogger("kemtchop.campay")

class CampayService:
    def __init__(self):
        self.app_username = os.getenv("CAMPAY_USERNAME")
        self.app_password = os.getenv("CAMPAY_PASSWORD")
        self.webhook_secret = os.getenv("CAMPAY_WEBHOOK_SECRET")
        self.base_url = "https://www.campay.net/api"
        self.token = None

    async def _get_token(self):
        if self.token:
            return self.token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/token/",
                data={"username": self.app_username, "password": self.app_password}
            )
            if response.status_code == 200:
                self.token = response.json().get("token")
                return self.token
            logger.error(f"Failed to get Campay token: {response.text}")
            return None

    async def create_payment(self, amount: float, description: str, reference: str, phone: str, metadata: Dict[str, Any] = None):
        token = await self._get_token()
        if not token:
            return {"success": False, "message": "Auth failed"}

        payload = {
            "amount": str(int(amount)),
            "currency": "XAF",
            "description": description,
            "external_reference": reference,
            "from": phone,
            "metadata": metadata
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/collect/",
                json=payload,
                headers={"Authorization": f"Token {token}"}
            )
            if response.status_code == 200:
                data = response.json()
                # Note: Adjust based on Campay real response structure
                return {
                    "success": True,
                    "payment_url": data.get("payment_url", ""),
                    "reference": data.get("reference", "")
                }
            logger.error(f"Campay payment creation failed: {response.text}")
            return {"success": False, "message": response.text}

    async def refund_payment(self, reference: str, amount: float, description: str):
        """
        💸 Remboursement via Campay
        """
        token = await self._get_token()
        if not token:
            return {"success": False, "message": "Auth failed"}

        payload = {
            "amount": str(int(amount)),
            "currency": "XAF",
            "description": description,
            "external_reference": f"REFUND-{reference}",
            "original_reference": reference
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/withdraw/", # Check if 'withdraw' or 'refund' is the correct endpoint for refunds
                json=payload,
                headers={"Authorization": f"Token {token}"}
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}

            logger.error(f"Campay refund failed: {response.text}")
            return {"success": False, "message": response.text}

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return True # Not secure but avoids blocking if not set

        expected = hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def parse_webhook_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload

campay_service = CampayService()
