# app/routes/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta
import logging

from app.database import get_db
from app.auth import check_permission
from app.entities.collective_pot import CollectivePot
from app.entities.suggestion import Suggestion
from app.enums import CollectivePotStatus

logger = logging.getLogger("kemtchop.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardSummary(BaseModel):
    total_hubs: int = 1
    active_productions: int = 0
    pending_orders: int = 0
    revenue_today: float = 0.0
    total_suggestions: int = 0
    total_collective_pots: int = 0
    pots_by_status: dict = {}
    hubs: list = []


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("dashboard")),
):
    """
    ✅ Résumé dashboard - Version blindée contre les colonnes manquantes.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    result = DashboardSummary()

    try:
        # 📊 Suggestions actives
        result.total_suggestions = db.query(func.count(Suggestion.id)).filter(
            Suggestion.is_active == True
        ).scalar() or 0

        # 📊 Total marmites
        result.total_collective_pots = db.query(func.count(CollectivePot.id)).scalar() or 0

        # 🔥 Productions actives
        active_statuses = [
            CollectivePotStatus.FUNDED.value,
            CollectivePotStatus.COOKING.value,
            CollectivePotStatus.DELIVERING.value,
        ]
        result.active_productions = db.query(func.count(CollectivePot.id)).filter(
            CollectivePot.status.in_(active_statuses)
        ).scalar() or 0

        # 🛒 Commandes en attente (via statut de la marmite, PAS via payment_status)
        pending_statuses = [
            CollectivePotStatus.ACTIVE.value,
            CollectivePotStatus.FUNDED.value,
            CollectivePotStatus.COOKING.value,
        ]
        result.pending_orders = db.execute(text("""
            SELECT COUNT(*) FROM orders o
            JOIN collective_pots cp ON o.collective_pot_id = cp.id
            WHERE cp.status IN :statuses
        """), {"statuses": tuple(pending_statuses)}).scalar() or 0

        # 💰 Revenu du jour (requête raw SQL pour éviter tout problème de mapping)
        revenue_result = db.execute(text("""
            SELECT COALESCE(SUM(total_amount), 0) FROM orders
            WHERE created_at >= :today AND created_at < :tomorrow
        """), {
            "today": f"{today.isoformat()} 00:00:00",
            "tomorrow": f"{tomorrow.isoformat()} 00:00:00"
        }).scalar()
        result.revenue_today = float(revenue_result or 0)

        # 📋 Répartition par statut
        for status in CollectivePotStatus:
            count = db.query(func.count(CollectivePot.id)).filter(
                CollectivePot.status == status.value
            ).scalar() or 0
            if count > 0:
                result.pots_by_status[status.value] = count

    except Exception as e:
        logger.error(f"❌ Erreur dashboard/summary: {e}", exc_info=True)
        # Retourner des zéros au lieu de crasher
        # L'admin affichera le fallback calculé localement

    return result