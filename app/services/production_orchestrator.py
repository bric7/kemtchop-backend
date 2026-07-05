# app/services/production_orchestrator.py
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.entities.collective_pot import CollectivePot
from app.entities.order import Order
from app.entities.collective_pot import CollectivePot  # ✅ Import corrigé
from app.enums import CampaignStatus, ProductionStatus, OrderStatus
from app.services.notification_service import NotificationService

logger = logging.getLogger("kemtchop.orchestrator")


class ProductionOrchestrator:
    """🏭 Orchestrateur de production culinaire - Modèle Kickstarter"""
    
    # ============================================================
    # 🎯 ÉTAPE 1 : VÉRIFIER SI DES CAMPAIGNS VIENNENT D'ÊTRE FUNDED
    # ============================================================
    @staticmethod
    def check_campaign_funding(db: Session) -> int:
        """✅ Vérifier si des Campaigns viennent d'atteindre leur seuil"""
        logger.info("[ORCHESTRATOR] 🎯 Vérification des campaigns funded...")
        
        # Campaigns qui viennent d'atteindre le seuil mais n'ont pas encore de CollectivePot
        candidates = db.query(Campaign).filter(
            Campaign.status == CampaignStatus.ACTIVE.value,
            Campaign.current_orders >= Campaign.minimum_orders,
            Campaign.collective_pot_id == None  # Pas encore de CollectivePot
        ).all()
        
        created = 0
        for campaign in candidates:
            # ✅ CRÉER AUTOMATIQUEMENT le CollectivePot
            collective_pot = CollectivePot(
                product_id=campaign.recipe_id,
                occurrence_date=campaign.target_date,
                status=ProductionStatus.CONFIRMED.value,
                minimum_production=campaign.minimum_orders,
                max_production=campaign.max_orders,
                reserved_portions=campaign.current_orders,
                pack_price=campaign.pack_price,
                individual_price=campaign.standard_price,
                launched_at=datetime.utcnow()
            )
            db.add(collective_pot)
            db.flush()  # Pour obtenir l'ID
            
            # ✅ Lier la Campaign au CollectivePot
            campaign.collective_pot_id = collective_pot.id
            campaign.status = CampaignStatus.FUNDED.value
            campaign.funded_at = datetime.utcnow()
            
            logger.info(
                "[ORCHESTRATOR] 🎉 Campaign '%s' funded ! CollectivePot #%s créé automatiquement",
                campaign.recipe.name, collective_pot.id
            )
            
            # 📢 Notifications
            NotificationService.notify_campaign_funded(db, campaign)
            created += 1
        
        db.commit()
        logger.info("[ORCHESTRATOR] ✅ %d campaigns funded, CollectivePots créés", created)
        return created
    
    # ============================================================
    # 🔒 ÉTAPE 2 : VERROUILLER LES MARMITTES À CAPACITÉ MAX
    # ============================================================
    @staticmethod
    def enforce_capacity_locks(db: Session) -> int:
        """✅ Verrouiller les CollectivePots ayant atteint leur capacité max"""
        logger.info("[ORCHESTRATOR] 🔒 Vérification des capacités maximales...")
        
        full_menus = db.query(CollectivePot).filter(
            CollectivePot.max_production.isnot(None),
            CollectivePot.reserved_portions >= CollectivePot.max_production,
            CollectivePot.status == ProductionStatus.CONFIRMED.value
        ).all()
        
        locked = 0
        for menu in full_menus:
            old_status = menu.status
            menu.status = ProductionStatus.READY.value  # Prêt pour cuisine
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
    
    # ============================================================
    # 🍳 ÉTAPE 3 : DÉMARRER MANUELLEMENT UNE PRODUCTION
    # ============================================================
    @staticmethod
    def launch_cooking(db: Session, menu_id: str) -> bool:
        """✅ Démarrer manuellement une production (dashboard admin)"""
        menu = db.query(CollectivePot).filter(CollectivePot.id == menu_id).first()
        if not menu:
            logger.warning("[ORCHESTRATOR] ❌ Menu %s introuvable", menu_id)
            return False
        
        if menu.status != ProductionStatus.CONFIRMED.value:
            logger.warning("[ORCHESTRATOR] ⚠️ Menu %s déjà en statut %s", menu_id, menu.status)
            return False
        
        menu.status = ProductionStatus.COOKING.value
        db.commit()
        
        logger.info("[ORCHESTRATOR] 🍳 %s lancé en cuisine par admin", menu.product.name)
        NotificationService.notify_production_confirmed(db, menu)
        return True
    
    # ============================================================
    # 📦 ÉTAPE 4 : MARQUER UNE PRODUCTION COMME PRÊTE
    # ============================================================
    @staticmethod
    def finish_cooking(db: Session, menu_id: str) -> bool:
        """✅ Marquer une production comme prête pour livraison"""
        menu = db.query(CollectivePot).filter(CollectivePot.id == menu_id).first()
        if not menu or menu.status != ProductionStatus.COOKING.value:
            return False
        
        menu.status = ProductionStatus.READY.value
        db.commit()
        
        logger.info("[ORCHESTRATOR] 📦 %s marqué comme prêt pour livraison", menu.product.name)
        return True
    
    # ============================================================
    # 🚫 ÉTAPE 5 : ANNULER UNE PRODUCTION
    # ============================================================
    @staticmethod
    def cancel_production(db: Session, menu_id: str, reason: str) -> bool:
        """✅ Annuler une production (avec notification clients)"""
        menu = db.query(CollectivePot).filter(CollectivePot.id == menu_id).first()
        if not menu:
            return False
        
        old_status = menu.status
        menu.status = ProductionStatus.CANCELLED.value
        menu.notes = f"Annulé : {reason}"
        db.commit()
        
        logger.warning(
            "[ORCHESTRATOR] 🚫 %s annulé (%s → %s) : %s",
            menu.product.name, old_status, menu.status, reason
        )
        NotificationService.notify_production_cancelled(db, menu, reason)
        return True
    
    # ============================================================
    # 📅 ÉTAPE 6 : EXPIRER LES CAMPAIGNS NON FUNDED
    # ============================================================
    @staticmethod
    def expire_old_campaigns(db: Session) -> int:
        """✅ Expirer les Campaigns qui n'ont pas atteint leur seuil à temps"""
        logger.info("[ORCHESTRATOR] 📅 Vérification des campaigns expirées...")
        
        today = datetime.utcnow().date()
        expired_campaigns = db.query(Campaign).filter(
            Campaign.status == CampaignStatus.ACTIVE.value,
            Campaign.target_date < today,  # Date passée
            Campaign.current_orders < Campaign.minimum_orders  # Seuil non atteint
        ).all()
        
        expired = 0
        for campaign in expired_campaigns:
            campaign.status = CampaignStatus.EXPIRED.value
            logger.info(
                "[ORCHESTRATOR] ⏰ Campaign '%s' expirée (%d/%d portions)",
                campaign.recipe.name,
                campaign.current_orders,
                campaign.minimum_orders
            )
            expired += 1
        
        db.commit()
        logger.info("[ORCHESTRATOR] ✅ %d campaigns expirées", expired)
        return expired