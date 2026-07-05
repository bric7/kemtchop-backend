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


class DashboardSummary(BaseModel):
    total_hubs: int = 1
    active_productions: int
    pending_orders: int
    revenue_today: float
    total_suggestions: int
    total_collective_pots: int
    pots_by_status: dict
    hubs: list = []


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("dashboard")),
):
    """
    ✅ Résumé dashboard avec données réelles.
    Adapté au schéma BDD actuel (sans payment_status).
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # 📊 Suggestions actives
    total_suggestions = db.query(func.count(Suggestion.id)).filter(
        Suggestion.is_active == True
    ).scalar() or 0

    # 📊 Total marmites
    total_collective_pots = db.query(func.count(CollectivePot.id)).scalar() or 0

    # 🔥 Productions actives
    active_statuses = [
        CollectivePotStatus.FUNDED.value,
        CollectivePotStatus.COOKING.value,
        CollectivePotStatus.DELIVERING.value,
    ]
    active_productions = db.query(func.count(CollectivePot.id)).filter(
        CollectivePot.status.in_(active_statuses)
    ).scalar() or 0

    # 🛒 Commandes en attente (basé sur collective_pot.status au lieu de payment_status)
    # Une commande est "pending" si sa marmite est encore en financement ou confirmée mais pas livrée
    pending_order_statuses = [
        CollectivePotStatus.ACTIVE.value,
        CollectivePotStatus.FUNDED.value,
        CollectivePotStatus.COOKING.value,
    ]
    pending_orders = db.query(func.count(Order.id)).join(
        CollectivePot, Order.collective_pot_id == CollectivePot.id
    ).filter(
        CollectivePot.status.in_(pending_order_statuses)
    ).scalar() or 0

    # 💰 Revenu du jour (somme des total_amount des orders créées aujourd'hui)
    revenue_today = db.query(
        func.coalesce(func.sum(Order.total_amount), 0.0)
    ).filter(
        Order.created_at >= f"{today.isoformat()} 00:00:00",
        Order.created_at < f"{tomorrow.isoformat()} 00:00:00",
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
        hubs=[],
    )