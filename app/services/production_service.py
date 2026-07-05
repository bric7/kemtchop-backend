# app/services/production_service.py
# ============================================================
# ⚙️ KEMTCHOP - Moteur d'Orchestration & Cycle de Vie Culinaire
# ============================================================

from sqlalchemy.orm import Session
from app.models.industrial_core import Production, CollectivePot
from app.models.order import Order
import datetime

class ProductionOrchestrator:

    @staticmethod
    def evaluate_voting_productions(db: Session):
        """
        🔄 AUTOMATE : Évalue les marmites en phase de vote.
        Si une marmite atteint son 'min_threshold', elle passe automatiquement en 'setup' (Mise en place).
        """
        voting_productions = db.query(Production).filter(
            Production.status == "voting"
        ).all()

        triggered_count = 0
        for prod in voting_productions:
            if prod.current_reserved >= prod.min_threshold:
                prod.status = "setup"
                prod.setup_at = datetime.datetime.utcnow()
                
                # 📢 Ici : Déclencher un hook de notification (ex: Push aux admins/chefs)
                # notification_service.notify_chef_marmite_validee(prod.id)
                
                # Mettre à jour le statut de toutes les commandes payées associées
                db.query(Order).filter(
                    Order.production_id == prod.id,
                    Order.status == "paid"
                ).update({"status": "reserved"})
                
                triggered_count += 1
                
        if triggered_count > 0:
            db.commit()
        return triggered_count

    @staticmethod
    def enforce_capacity_locks(db: Session):
        """
        🔒 VERROUILLAGE : Si une marmite atteint sa capacité maximale ('max_capacity'),
        on ferme immédiatement les vannes pour cette production.
        """
        # On cherche les productions ouvertes qui ont fait le plein
        full_productions = db.query(Production).filter(
            Production.status.in_(["voting", "setup"]),
            Production.current_reserved >= Production.max_capacity
        ).all()

        locked_count = 0
        for prod in full_productions:
            # Si elle était encore en vote, on la force en setup ou lock
            if prod.status == "voting":
                prod.status = "setup"
                prod.setup_at = datetime.datetime.utcnow()
            
            # 📢 Optionnel : On peut envoyer un signal pour désactiver l'affichage mobile 
            # du CollectivePot lié pour éviter des clics inutiles.
            locked_count += 1

        if locked_count > 0:
            db.commit()
        return locked_count

    @staticmethod
    def propagate_production_status(db: Session, production_id: int, new_status: str):
        """
        ⚡ PROPAGATION : Quand le chef clique sur "Lancer Cuisson" ou "Prêt", 
        le statut cascade instantanément sur l'ensemble des commandes du lot.
        """
        production = db.query(Production).filter(Production.id == production_id).first()
        if not production:
            return False

        # Mise à jour de la marmite physique
        production.status = new_status
        
        # Horodatage selon l'étape
        if new_status == "cooking":
            production.cooking_started_at = datetime.datetime.utcnow()
            order_target_status = "cooking"
        elif new_status == "ready":
            production.packaging_started_at = datetime.datetime.utcnow()
            order_target_status = "ready"
        elif new_status == "dispatched":
            production.dispatched_at = datetime.datetime.utcnow()
            order_target_status = "out_for_delivery"
        else:
            order_target_status = None

        # Cascade sur les commandes individuelles des clients du lot
        if order_target_status:
            db.query(Order).filter(
                Order.production_id == production_id,
                Order.status.in_(["reserved", "cooking", "ready"]) # Sécurité statut
            ).update({"status": order_target_status})

        db.commit()
        return True