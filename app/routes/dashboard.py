# app/routes/dashboard.py
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.auth import check_permission

# ============================================================
# 🏗️ ROUTER DEFINITION (MANQUANT - Cause du NameError)
# ============================================================
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============================================================
# 📊 SCHEMAS DE RÉPONSE
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
    total_hubs: int
    active_productions: int
    pending_orders: int
    revenue_today: float
    hubs: List[HubSummary]


class HubFilter(BaseModel):
    city: Optional[str] = None
    hub_id: Optional[str] = None


# ============================================================
# 🔍 IMPORT DES ENTITÉS (Ajuster selon votre structure réelle)
# ============================================================
# ⚠️ IMPORTANT : Vérifiez que Hub existe dans vos entités
# Si Hub n'existe pas encore, créez-le ou adaptez ce endpoint
try:
    from app.entities.hub import Hub
except ImportError:
    # Fallback si Hub n'existe pas encore
    Hub = None


# ============================================================
# 📱 ENDPOINTS
# ============================================================
@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    filters: HubFilter = Depends(),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("dashboard"))
):
    """
    ✅ Résumé du dashboard admin
    
    Retourne les statistiques globales par hub :
    - Nombre total de hubs
    - Productions actives
    - Commandes en attente
    - Revenu du jour
    """
    # ⚠️ Protection si l'entité Hub n'existe pas encore
    if Hub is None:
        return DashboardSummary(
            total_hubs=0,
            active_productions=0,
            pending_orders=0,
            revenue_today=0.0,
            hubs=[]
        )
    
    query = db.query(Hub)
    
    if filters.city:
        query = query.filter(Hub.city == filters.city)
    if filters.hub_id:
        query = query.filter(Hub.id == filters.hub_id)
    
    hubs = query.all()
    
    return DashboardSummary(
        total_hubs=len(hubs),
        active_productions=sum(getattr(h, 'active_productions', 0) for h in hubs),
        pending_orders=sum(getattr(h, 'pending_orders', 0) for h in hubs),
        revenue_today=sum(getattr(h, 'revenue_today', 0.0) for h in hubs),
        hubs=[HubSummary.model_validate(h) for h in hubs]
    )