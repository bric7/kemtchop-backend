# app/schemas/dashboard.py
class HubFilter(BaseModel):
    city: Optional[str] = Field(None, example="Yaoundé")
    hub_id: Optional[int] = Field(None, description="Filtrer par hub spécifique")
    status: Optional[ProductionStatus] = Field(None)
    date_from: Optional[date] = Field(None)
    date_to: Optional[date] = Field(None)

class DashboardSummary(BaseModel):
    total_hubs: int
    active_productions: int
    pending_orders: int
    revenue_today: float
    hubs: List[HubSummary]

class HubSummary(BaseModel):
    id: int
    name: str
    city: str
    active_menus: int
    pending_orders: int
    capacity_usage: float  # 0.0 à 1.0