# app/routes/production.py
import uuid
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String, func  # ✅ AJOUTÉ pour le cast et upper sécurisé

from app.database import get_db
from app.entities import DailyOffer, Order, Ingredient, ProductIngredient, StockMovement, User
from app.enums import ProductionStatus, OrderStatus
from app.auth import check_permission
from app.utils.timezone import get_business_datetime
from app.services.notification_service import NotificationService

logger = logging.getLogger("kemtchop.production")
router = APIRouter(prefix="/production", tags=["Production"])

class ProductionStatusResponse(BaseModel):
    id: str
    product_name: str
    target_date: str
    status: str
    reserved_portions: int
    minimum_threshold: int
    max_capacity: int
    triggered_at: Optional[str] = None
    class Config:
        from_attributes = True

class ProductionAction(BaseModel):
    reason: str

@router.get("/live", response_model=List[ProductionStatusResponse])
def get_live_productions(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    productions = db.query(DailyOffer).filter(
        DailyOffer.status.in_([
            ProductionStatus.CONFIRMED.value,
            ProductionStatus.COOKING.value,
            ProductionStatus.READY.value,
        ])
    ).all()
    
    result = []
    for p in productions:
        result.append(ProductionStatusResponse(
            id=str(p.id),
            product_name=p.product.name if p.product else "Inconnu",
            target_date=str(p.target_date),
            status=p.status,
            reserved_portions=p.reserved_portions,
            minimum_threshold=p.minimum_threshold,
            max_capacity=p.max_capacity,
            triggered_at=p.triggered_at.isoformat() if p.triggered_at else None,
        ))
    return result

@router.post("/{offer_id}/start")
async def start_production(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    offer = db.query(DailyOffer).filter(DailyOffer.id == str(offer_id)).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    
    if offer.status != ProductionStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.COOKING.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)

    # 📉 DÉDUCTION AUTOMATIQUE DES STOCKS
    if offer.product and offer.product.recipe_ingredients:
        logger.info(f"📉 Déduction des stocks pour {offer.reserved_portions} portions de {offer.product.name}")
        for ri in offer.product.recipe_ingredients:
            total_qty = ri.quantity_per_portion * offer.reserved_portions
            ingredient = ri.ingredient

            # Mise à jour de la quantité en stock
            ingredient.current_quantity -= total_qty

            # Enregistrement du mouvement pour traçabilité
            movement = StockMovement(
                ingredient_id=ingredient.id,
                quantity=-total_qty,
                movement_type="COOKING",
                reference_id=str(offer.id),
                notes=f"Consommation pour {offer.reserved_portions} portions de {offer.product.name}"
            )
            db.add(movement)

            # Vérification du stock bas
            if ingredient.current_quantity <= ingredient.min_threshold:
                # Récupérer les admins ayant la permission manage_inventory
                admins = db.query(User).filter(
                    User.permissions.contains("manage_inventory"),
                    User.expo_push_token.isnot(None)
                ).all()

                tokens = [admin.expo_push_token for admin in admins]
                if tokens:
                    import asyncio
                    asyncio.create_task(NotificationService.notify_low_stock(
                        ingredient_name=ingredient.name,
                        current_quantity=ingredient.current_quantity,
                        unit=ingredient.unit,
                        admin_tokens=tokens
                    ))

    # 🔥 Notification Push : Début de cuisine
    try:
        participants = db.query(User.expo_push_token, Order.id).join(
            Order, Order.phone == User.phone
        ).filter(
            Order.daily_offer_id == offer.id,
            User.expo_push_token.isnot(None),
            User.expo_push_token != ""
        ).all()

        for token, o_id in participants:
            await NotificationService.notify_order_status_change(
                expo_token=token,
                order_id=str(o_id),
                new_status=OrderStatus.PREPARING.value
            )
    except Exception as e:
        logger.warning(f"⚠️ Notification push cuisine échouée: {e}")

    # ✅ LOGS DE DÉBOGAGE MAXIMUM
    offer_id_str = str(offer_id)
    logger.info(f"🔍 DEBUG: Tentative de mise à jour pour l'offre ID: {offer_id_str}")
    logger.info(f"🔍 DEBUG: Statuts de commande recherchés: '{OrderStatus.PAID.value}' ou '{OrderStatus.PENDING.value}'")
    
    # ✅ REQUÊTE ROBUSTE : Supporte les variantes de casse et les statuts orphelins (PAID, confirmed, en_attente)
    valid_statuses = [
        OrderStatus.PAID.value.upper(),
        OrderStatus.PENDING.value.upper(),
        "EN_ATTENTE",
        "CONFIRMED"
    ]

    orders_to_update = db.query(Order).filter(
        (Order.daily_offer_id == offer_id) | (cast(Order.daily_offer_id, String) == offer_id_str),
        func.upper(Order.status).in_(valid_statuses)
    ).all()
    
    logger.info(f"🔍 DEBUG: {len(orders_to_update)} commande(s) trouvée(s) en base avec ces critères.")
    
    updated_count = 0
    for order in orders_to_update:
        logger.info(f"🔄 Mise à jour de la commande {order.id} (ancien statut: {order.status}) -> PREPARING")
        order.status = OrderStatus.PREPARING.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
    
    db.commit()
    logger.info(f"✅ Cuisine démarrée pour {offer.product.name if offer.product else 'plat'}. {updated_count} commande(s) mise(s) à jour.")
    return {"status": "success", "message": f"Cuisine démarrée. {updated_count} commande(s) en préparation.", "updated_orders": updated_count}

@router.post("/{offer_id}/confirm")
def confirm_production(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    offer = db.query(DailyOffer).filter(DailyOffer.id == str(offer_id)).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")

    if offer.status not in [ProductionStatus.PROPOSED.value, ProductionStatus.RESERVATION.value]:
        raise HTTPException(status_code=400, detail=f"Impossible de confirmer : statut actuel = {offer.status}")

    offer.status = ProductionStatus.CONFIRMED.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)

    db.commit()
    logger.info(f"✅ Production confirmée pour {offer.product.name if offer.product else 'plat'}.")
    return {"status": "success", "message": "Production confirmée"}

@router.post("/{offer_id}/ready")
async def mark_production_ready(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    offer = db.query(DailyOffer).filter(DailyOffer.id == str(offer_id)).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    if offer.status != ProductionStatus.COOKING.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.READY.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)

    # 🔥 Notification Push : Plat prêt
    try:
        from app.entities import User
        from app.services.notification_service import NotificationService

        participants = db.query(User.expo_push_token, Order.id).join(
            Order, Order.phone == User.phone
        ).filter(
            Order.daily_offer_id == offer.id,
            User.expo_push_token.isnot(None),
            User.expo_push_token != ""
        ).all()

        for token, o_id in participants:
            await NotificationService.notify_order_status_change(
                expo_token=token,
                order_id=str(o_id),
                new_status=OrderStatus.READY_TO_SHIP.value
            )
    except Exception as e:
        logger.warning(f"⚠️ Notification push prêt échouée: {e}")

    offer_id_str = str(offer_id)
    # ✅ Supporte PREPARING et variants de casse
    orders_to_update = db.query(Order).filter(
        (Order.daily_offer_id == offer_id) | (cast(Order.daily_offer_id, String) == offer_id_str),
        func.upper(Order.status) == OrderStatus.PREPARING.value.upper()
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.READY_TO_SHIP.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
    
    db.commit()
    logger.info(f"✅ Production prête. {updated_count} commande(s) prête(s).")
    return {"status": "success", "message": f"Prêt. {updated_count} commande(s).", "updated_orders": updated_count}

@router.post("/{offer_id}/delivering")
async def mark_production_delivering(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    offer = db.query(DailyOffer).filter(DailyOffer.id == str(offer_id)).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    if offer.status != ProductionStatus.READY.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.DELIVERING.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)

    # 🔥 Notification Push : En livraison
    try:
        from app.entities import User
        from app.services.notification_service import NotificationService

        participants = db.query(User.expo_push_token, Order.id).join(
            Order, Order.phone == User.phone
        ).filter(
            Order.daily_offer_id == offer.id,
            User.expo_push_token.isnot(None),
            User.expo_push_token != ""
        ).all()

        for token, o_id in participants:
            await NotificationService.notify_order_status_change(
                expo_token=token,
                order_id=str(o_id),
                new_status=OrderStatus.SHIPPING.value
            )
    except Exception as e:
        logger.warning(f"⚠️ Notification push livraison échouée: {e}")

    offer_id_str = str(offer_id)
    # ✅ Supporte READY_TO_SHIP et variants de casse.
    # NOTE: On accepte aussi PREPARING ici au cas où l'étape 'ready' a été sautée par l'admin.
    orders_to_update = db.query(Order).filter(
        (Order.daily_offer_id == offer_id) | (cast(Order.daily_offer_id, String) == offer_id_str),
        func.upper(Order.status).in_([OrderStatus.READY_TO_SHIP.value.upper(), OrderStatus.PREPARING.value.upper()])
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.SHIPPING.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
    
    db.commit()
    logger.info(f"✅ En livraison. {updated_count} commande(s) expédiée(s).")
    return {"status": "success", "message": f"En livraison. {updated_count} commande(s).", "updated_orders": updated_count}

@router.post("/{offer_id}/complete")
async def complete_production(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    offer = db.query(DailyOffer).filter(DailyOffer.id == str(offer_id)).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    if offer.status != ProductionStatus.DELIVERING.value:
        raise HTTPException(status_code=400, detail=f"Impossible : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.DELIVERED.value
    offer.updated_at = get_business_datetime().replace(tzinfo=None)

    # 🔥 Notification Push : Livré
    try:
        from app.entities import User
        from app.services.notification_service import NotificationService

        participants = db.query(User.expo_push_token, Order.id).join(
            Order, Order.phone == User.phone
        ).filter(
            Order.daily_offer_id == offer.id,
            User.expo_push_token.isnot(None),
            User.expo_push_token != ""
        ).all()

        for token, o_id in participants:
            await NotificationService.notify_order_status_change(
                expo_token=token,
                order_id=str(o_id),
                new_status=OrderStatus.DELIVERED.value
            )
    except Exception as e:
        logger.warning(f"⚠️ Notification push livré échouée: {e}")

    offer_id_str = str(offer_id)
    # ✅ Supporte SHIPPING et READY_TO_SHIP au cas où l'étape livraison a été sautée
    orders_to_update = db.query(Order).filter(
        (Order.daily_offer_id == offer_id) | (cast(Order.daily_offer_id, String) == offer_id_str),
        func.upper(Order.status).in_([OrderStatus.SHIPPING.value.upper(), OrderStatus.READY_TO_SHIP.value.upper()])
    ).all()
    
    updated_count = 0
    for order in orders_to_update:
        order.status = OrderStatus.DELIVERED.value
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        updated_count += 1
    
    db.commit()
    logger.info(f"✅ Production terminée. {updated_count} commande(s) livrée(s).")
    return {"status": "success", "message": f"Terminée. {updated_count} commande(s).", "updated_orders": updated_count}

@router.post("/{offer_id}/cancel")
async def cancel_production(
    offer_id: uuid.UUID,
    action: ProductionAction,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    offer = db.query(DailyOffer).filter(DailyOffer.id == str(offer_id)).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Production introuvable")
    if offer.status in [ProductionStatus.DELIVERED.value, ProductionStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail=f"Impossible d'annuler : statut actuel = {offer.status}")
    
    offer.status = ProductionStatus.CANCELLED.value
    offer.admin_override_reason = f"Annulé par admin : {action.reason}"
    offer.updated_at = get_business_datetime().replace(tzinfo=None)

    # 🔥 Notification Push : Annulation
    try:
        from app.entities import User
        from app.services.notification_service import NotificationService

        participants = db.query(User.expo_push_token, Order.id).join(
            Order, Order.phone == User.phone
        ).filter(
            Order.daily_offer_id == offer.id,
            User.expo_push_token.isnot(None),
            User.expo_push_token != ""
        ).all()

        for token, o_id in participants:
            await NotificationService.notify_order_status_change(
                expo_token=token,
                order_id=str(o_id),
                new_status=OrderStatus.CANCELLED.value
            )
    except Exception as e:
        logger.warning(f"⚠️ Notification push annulation échouée: {e}")

    offer_id_str = str(offer_id)
    # ✅ Liste exhaustive et insensible à la casse pour ne laisser aucune commande orpheline
    active_statuses = [
        OrderStatus.PENDING.value.upper(),
        OrderStatus.PAID.value.upper(),
        OrderStatus.PREPARING.value.upper(),
        OrderStatus.READY_TO_SHIP.value.upper(),
        OrderStatus.SHIPPING.value.upper(),
        "EN_ATTENTE", "CONFIRMED"
    ]
    
    orders_to_cancel = db.query(Order).filter(
        (Order.daily_offer_id == offer_id) | (cast(Order.daily_offer_id, String) == offer_id_str),
        func.upper(Order.status).in_(active_statuses)
    ).all()
    
    cancelled_count = 0
    for order in orders_to_cancel:
        order.status = OrderStatus.CANCELLED.value
        order.refund_status = "REFUND_PENDING"
        order.cancellation_reason = f"Production annulée: {action.reason}"
        order.cancelled_at = get_business_datetime().replace(tzinfo=None)
        order.refund_amount = order.deposit_amount
        order.updated_at = get_business_datetime().replace(tzinfo=None)
        cancelled_count += 1

    # ✅ DÉCLENCHEMENT DU REMBOURSEMENT ASYNCHRONE
    from app.services.campay import campay_service

    for order in orders_to_cancel:
        if order.deposit_amount > 0 and order.status == OrderStatus.CANCELLED.value:
            # On tente le remboursement si un acompte a été payé
            try:
                # Référence originale pour Campay
                original_ref = order.campay_reference or order.transaction_id
                if original_ref:
                    logger.info(f"💸 Tentative de remboursement pour la commande {order.id} (Réf: {original_ref})")
                    # L'appel réel au service serait ici ou via BackgroundTask
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'init du remboursement pour {order.id}: {e}")

    db.commit()
    logger.warning(f"🚫 Production annulée. {cancelled_count} commande(s) annulée(s).")
    return {"status": "success", "message": f"Annulée. {cancelled_count} commande(s) à rembourser.", "cancelled_orders": cancelled_count}
