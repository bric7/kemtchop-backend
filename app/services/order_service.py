# app/services/order_service.py
from sqlalchemy.exc import IntegrityError

class OrderService:
    @staticmethod
    def reserve_portion(db: Session, user_phone: str, payload: ReserveOrderRequest) -> ReserveOrderResponse:
        """✅ Réservation atomique : soit tout réussit, soit rien ne change"""
        
        try:
            # 🔒 Verrouillage pessimiste pour éviter les race conditions
            menu = db.query(DailyMenu).filter(
                DailyMenu.id == payload.daily_menu_id
            ).with_for_update().first()
            
            if not menu or not menu.can_accept_orders:
                return ReserveOrderResponse(
                    success=False,
                    message="Ce menu n'accepte plus de réservations"
                )
            
            # Vérification capacité
            if menu.remaining_capacity and payload.portions > menu.remaining_capacity:
                return ReserveOrderResponse(
                    success=False,
                    message=f"Capacité insuffisante : {menu.remaining_capacity} places restantes"
                )
            
            # 🔄 DÉBUT TRANSACTION ATOMIQUE
            with db.begin():
                # 1. Créer la commande
                new_order = Order(
                    user_phone=user_phone,
                    daily_menu_id=menu.id,
                    portions=payload.portions,
                    price_paid=menu.individual_price * payload.portions,
                    delivery_zone=payload.delivery_zone,
                    complement=payload.complement,
                    affiliate_code=payload.affiliate_code,
                    status=OrderStatus.PENDING
                )
                db.add(new_order)
                db.flush()  # ← Génère l'ID sans commit
                
                # 2. Incrémenter le compteur du menu
                menu.reserved_portions += payload.portions
                
                # 3. Transition auto si seuil atteint
                if menu.status == ProductionStatus.PUBLISHED and menu.reserved_portions >= menu.minimum_production:
                    menu.status = ProductionStatus.CONFIRMED
                    menu.confirmed_at = datetime.utcnow()
                    
                    # 📢 Publier événement pour notifications
                    from app.services.event_bus import EventBus
                    EventBus.publish("production.confirmed", {
                        "menu_id": menu.id,
                        "product_name": menu.product.name,
                        "hub": menu.hub_id,
                        "triggered_by_order_id": new_order.id
                    })
            
            # ✅ Transaction commitée : toutes les modifications sont persistées
            return ReserveOrderResponse(
                success=True,
                order_id=new_order.id,
                remaining_capacity=menu.remaining_capacity,
                message="Réservation confirmée",
                next_status=menu.status.value if isinstance(menu.status, ProductionStatus) else menu.status
            )
            
        except IntegrityError:
            db.rollback()
            logger.error("[ORDER] Conflit de réservation pour menu %d", payload.daily_menu_id)
            return ReserveOrderResponse(success=False, message="Conflit de réservation. Veuillez réessayer.")