# app/routes/dashboard.py
@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    filters: HubFilter = Depends(),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("dashboard"))
):
    query = db.query(Hub)
    
    if filters.city:
        query = query.filter(Hub.city == filters.city)
    if filters.hub_id:
        query = query.filter(Hub.id == filters.hub_id)
    
    hubs = query.all()
    
    return DashboardSummary(
        total_hubs=len(hubs),
        active_productions=sum(h.active_productions for h in hubs),
        pending_orders=sum(h.pending_orders for h in hubs),
        revenue_today=sum(h.revenue_today for h in hubs),
        hubs=[HubSummary.from_orm(h) for h in hubs]
    )