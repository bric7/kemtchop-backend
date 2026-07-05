# app/routes/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta

from app.database import get_db
from app.auth import check_permission
from app.entities.collective_pot import CollectivePot
from app.entities.suggestion import Suggestion
from app.entities.order import Order
from app.enums import CollectivePotStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============================================================
# 📊 SCHEMAS
# ============================================================
class HubSummary(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    active_productions: int = 0
    pending_orders: int = 0
    revenue_today: float = 0.0

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    total_hubs: int = 1  # Single hub for now
    active_productions: int
    pending_orders: int
    revenue_today: float
    total_suggestions: int
    total_collective_pots: int
    pots_by_status: dict
    hubs: List[HubSummary] = []


# ============================================================
# 📱 ENDPOINT
# ============================================================
@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("dashboard")),
):
    """
    ✅ Résumé du dashboard admin avec données réelles.
    
    Retourne :
    - Productions actives (funded + cooking + delivering)
    - Commandes en attente (orders non livrées)
    - Revenu du jour
    - Suggestions actives
    - Répartition des marmites par statut
    """
    today = date.today()

    # 📊 Compteurs globaux
    total_suggestions = db.query(func.count(Suggestion.id)).filter(
        Suggestion.is_active == True
    ).scalar() or 0

    total_collective_pots = db.query(func.count(CollectivePot.id)).scalar() or 0

    # 🔥 Productions actives (funded, cooking, delivering)
    active_statuses = [
        CollectivePotStatus.FUNDED.value,
        CollectivePotStatus.COOKING.value,
        CollectivePotStatus.DELIVERING.value,
    ]
    active_productions = db.query(func.count(CollectivePot.id)).filter(
        CollectivePot.status.in_(active_statuses)
    ).scalar() or 0

    # 🛒 Commandes en attente (non livrées, non annulées)
    pending_orders = db.query(func.count(Order.id)).filter(
        Order.payment_status != "refunded",
        Order.payment_status != "cancelled",
    ).scalar() or 0

    # 💰 Revenu du jour (orders créées aujourd'hui)
    tomorrow = today + timedelta(days=1)
    revenue_today = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
        Order.created_at >= today.isoformat(),
        Order.created_at < tomorrow.isoformat(),
    ).scalar() or 0.0

    # 📋 Répartition par statut
    status_counts = {}
    for status in CollectivePotStatus:
        count = db.query(func.count(CollectivePot.id)).filter(
            CollectivePot.status == status.value
        ).scalar() or 0
        if count > 0:
            status_counts[status.value] = count

    return DashboardSummary(
        total_hubs=1,
        active_productions=active_productions,
        pending_orders=pending_orders,
        revenue_today=float(revenue_today),
        total_suggestions=total_suggestions,
        total_collective_pots=total_collective_pots,
        pots_by_status=status_counts,
        hubs=[],  # Multi-hub à implémenter plus tard
    )