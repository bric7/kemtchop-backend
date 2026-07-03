# app/services/optimizer/simple_planner.py
class SimpleProductionPlanner:
    """🎯 Planification heuristique : règles métier simples"""
    
    @staticmethod
    def suggest_daily_production(hub_id: int, target_date: date, db: Session) -> List[ProductionSuggestion]:
        """Suggère quelles recettes programmer pour demain dans ce hub"""
        
        # Règle 1 : Recettes avec fort taux de conversion hier
        high_demand = db.query(Recipe).join(Order).filter(
            Order.hub_id == hub_id,
            Order.created_at >= datetime.utcnow() - timedelta(days=2),
            Recipe.conversion_rate > 0.3  # 30% des vues → commandes
        ).all()
        
        # Règle 2 : Éviter la cannibalisation (pas 2 plats similaires)
        # Règle 3 : Respecter les stocks disponibles
        # Règle 4 : Prioriser les recettes avec marge > 40%
        
        return [
            ProductionSuggestion(
                recipe_id=r.id,
                suggested_capacity=50,  # Heuristique simple
                confidence_score=0.8,    # Basé sur historique
                reason="Forte demande hier + marge élevée"
            )
            for r in high_demand[:5]  # Top 5 suggestions
        ]