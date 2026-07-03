# app/services/production_orchestrator.py
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.entities.daily_menu import DailyMenu
from app.entities.order import Order
from app.enums import ProductionStatus, OrderStatus  # ✅ NOUVEAUX IMPORTS
from app.services.notification_service import NotificationService

logger = logging.getLogger("kemtchop.orchestrator")

class ProductionOrchestrator:
    """🏭 Orchestrateur de production culinaire - Méthodes atomiques"""
    
    @staticmethod
    def evaluate_voting_productions(db: Session) -> int:
        """✅ Étape 1 : Détecter les DailyMenu ayant atteint leur seuil"""
        logger.info("[ORCHESTRATOR] 📊 Évaluation des seuils de production...")
        
        # ✅ Utiliser les valeurs d'enum dans les filtres
        candidates = db.query(DailyMenu).filter(
            DailyMenu.status == ProductionStatus.PUBLISHED.value,
            DailyMenu.reserved_portions >= DailyMenu.minimum_production,
            DailyMenu.occurrence_date == datetime.utcnow().date() + timedelta(days=1)
        ).all()
        
        triggered = 0
        for menu in candidates:
            old_status = menu.status
            
            # ✅ Transition via enum
            menu.status = ProductionStatus.CONFIRMED.value
            menu.launched_at = datetime.utcnow()
            db.add(menu)
            
            logger.info(
                "[ORCHESTRATOR] 🚀 %s : seuil atteint (%d/%d) → %s → %s",
                menu.product.name,
                menu.reserved_portions,
                menu.minimum_production,
                old_status,
                menu.status
            )
            triggered += 1
            
            # 📢 Notification via EventBus (à implémenter)
            # EventBus.publish("production.confirmed", {"menu_id": menu.id, ...})
            NotificationService.notify_production_confirmed(db, menu)
        
        db.commit()
        logger.info("[ORCHESTRATOR] ✅ %d productions déclenchées", triggered)
        return triggered
    
    @staticmethod
    def enforce_capacity_locks(db: Session) -> int:
        """✅ Étape 2 : Verrouiller les marmites ayant atteint leur capacité max"""
        logger.info("[ORCHESTRATOR] 🔒 Vérification des capacités maximales...")
        
        full_menus = db.query(DailyMenu).filter(
            DailyMenu.max_production.isnot(None),
            DailyMenu.reserved_portions >= DailyMenu.max_production,
            DailyMenu.status == ProductionStatus.CONFIRMED.value  # ✅ Enum value
        ).all()
        
        locked = 0
        for menu in full_menus:
            old_status = menu.status
            
            # ✅ Transition vers CLOSED via enum
            menu.status = ProductionStatus.CANCELLED.value  # ou PRODUCTION_CLOSED si tu l'as ajouté
            db.add(menu)
            
            logger.info(
                "[ORCHESTRATOR] 🔒 %s : capacité max atteinte (%d/%d) → %s → %s",
                menu.product.name,
                menu.reserved_portions,
                menu.max_production,
                old_status,
                menu.status
            )
            locked += 1
        
        db.commit()
        logger.info("[ORCHESTRATOR] ✅ %d marmites verrouillées (capacité max)", locked)
        return locked
    
    @staticmethod
    def launch_cooking(db: Session, menu_id: str) -> bool:
        """✅ Étape 3 : Démarrer manuellement une production (dashboard admin)"""
        menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
        if not menu:
            logger.warning("[ORCHESTRATOR] ❌ Menu %s introuvable", menu_id)
            return False
        
        # ✅ Comparaison avec enum value
        if menu.status != ProductionStatus.PUBLISHED.value:
            logger.warning("[ORCHESTRATOR] ⚠️ Menu %s déjà en statut %s", menu_id, menu.status)
            return False
        
        # ✅ Transition via enum
        menu.status = ProductionStatus.CONFIRMED.value
        menu.launched_at = datetime.utcnow()
        db.commit()
        
        logger.info("[ORCHESTRATOR] 🍳 %s lancé manuellement par admin", menu.product.name)
        NotificationService.notify_production_confirmed(db, menu)
        return True
    
    @staticmethod
    def finish_cooking(db: Session, menu_id: str) -> bool:
        """✅ Étape 4 : Marquer une production comme prête pour livraison"""
        menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
        if not menu or menu.status != ProductionStatus.CONFIRMED.value:
            return False
        
        # ✅ Transition vers READY via enum
        menu.status = ProductionStatus.READY.value
        db.commit()
        
        logger.info("[ORCHESTRATOR] 📦 %s marqué comme prêt pour livraison", menu.product.name)
        return True
    
    @staticmethod
    def cancel_production(db: Session, menu_id: str, reason: str) -> bool:
        """✅ Étape 5 : Annuler une production (avec notification clients)"""
        menu = db.query(DailyMenu).filter(DailyMenu.id == menu_id).first()
        if not menu:
            return False
        
        old_status = menu.status
        
        # ✅ Transition vers CANCELLED via enum
        menu.status = ProductionStatus.CANCELLED.value
        menu.notes = f"Annulé : {reason}"
        db.commit()
        
        logger.warning(
            "[ORCHESTRATOR] 🚫 %s annulé (%s → %s) : %s",
            menu.product.name, old_status, menu.status, reason
        )
        NotificationService.notify_production_cancelled(db, menu, reason)
        return True