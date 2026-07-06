# app/routes/campaigns.py
import logging
from datetime import date, timedelta, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.entities.collective_pot import CollectivePot
from app.entities.product import Product
from app.enums import CollectivePotStatus
# ✅ CORRIGÉ : RecipeSummary → ProductSummary
from app.schemas.campaign import CampaignCreate, CampaignResponse, ProductSummary
from app.auth import check_permission

logger = logging.getLogger("kemtchop.campaigns")

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


# ============================================================
# 📱 ENDPOINTS PUBLICS
# ============================================================

@router.get("/tomorrow", response_model=List[CampaignResponse])
def get_tomorrow_campaigns(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None),
    funded_only: bool = Query(False),
    active_only: bool = Query(True),
):
    tomorrow = date.today() + timedelta(days=1)

    query = db.query(CollectivePot).options(
        joinedload(CollectivePot.product)
    ).filter(CollectivePot.target_date == tomorrow)

    if active_only and not funded_only:
        query = query.filter(CollectivePot.status == CollectivePotStatus.ACTIVE.value)
    elif funded_only:
        query = query.filter(CollectivePot.status == CollectivePotStatus.FUNDED.value)
    else:
        query = query.filter(
            CollectivePot.status.in_([
                CollectivePotStatus.ACTIVE.value,
                CollectivePotStatus.FUNDED.value,
            ])
        )

    if category and category != "Tout":
        query = query.join(Product).filter(Product.category == category)

    pots = query.all()

    result = []
    for pot in pots:
        result.append(CampaignResponse(
            id=str(pot.id),
            # ✅ CORRIGÉ : recipe → product
            product=ProductSummary(
                id=pot.product.id,
                name=pot.product.name,
                category=pot.product.category,
                image_url=pot.product.image_url,
            ),
            target_date=pot.target_date,
            status=pot.status,
            minimum_orders=pot.minimum_orders,
            max_orders=pot.max_orders,
            current_orders=pot.current_orders,
            current_revenue=float(pot.current_revenue),
            preorder_price=float(pot.preorder_price),
            live_price=float(pot.live_price),
            sponsor_pack_price=float(pot.sponsor_pack_price),
            discount_percentage=float(pot.discount_percentage),
            display_price=float(pot.display_price),
            progress_percentage=float(pot.progress_percentage),
            remaining_to_fund=int(pot.remaining_to_fund),
            remaining_capacity=int(pot.remaining_capacity),
            remaining_amount=float(pot.remaining_amount),
            bonus_description=pot.bonus_description,
            is_funded=pot.is_funded,
            is_active=pot.is_active,
            funded_at=pot.funded_at,
            created_at=pot.created_at,
            updated_at=pot.updated_at,
        ))

    result.sort(key=lambda x: x.progress_percentage, reverse=True)
    logger.info(f"📊 {len(result)} collective pots pour demain")
    return result


@router.get("/today", response_model=List[CampaignResponse])
def get_today_campaigns(db: Session = Depends(get_db)):
    today = date.today()
    pots = (
        db.query(CollectivePot)
        .options(joinedload(CollectivePot.product))
        .filter(
            CollectivePot.target_date == today,
            CollectivePot.status.in_([
                CollectivePotStatus.ACTIVE.value,
                CollectivePotStatus.FUNDED.value,
            ]),
        )
        .all()
    )

    return [
        CampaignResponse(
            id=str(p.id),
            # ✅ CORRIGÉ : recipe → product
            product=ProductSummary(
                id=p.product.id,
                name=p.product.name,
                category=p.product.category,
                image_url=p.product.image_url,
            ),
            target_date=p.target_date,
            status=p.status,
            minimum_orders=p.minimum_orders,
            max_orders=p.max_orders,
            current_orders=p.current_orders,
            current_revenue=float(p.current_revenue),
            preorder_price=float(p.preorder_price),
            live_price=float(p.live_price),
            sponsor_pack_price=float(p.sponsor_pack_price),
            discount_percentage=float(p.discount_percentage),
            display_price=float(p.display_price),
            progress_percentage=float(p.progress_percentage),
            remaining_to_fund=int(p.remaining_to_fund),
            remaining_capacity=int(p.remaining_capacity),
            remaining_amount=float(p.remaining_amount),
            bonus_description=p.bonus_description,
            is_funded=p.is_funded,
            is_active=p.is_active,
            funded_at=p.funded_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in pots
    ]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign_detail(campaign_id: str, db: Session = Depends(get_db)):
    pot = (
        db.query(CollectivePot)
        .options(joinedload(CollectivePot.product))
        .filter(CollectivePot.id == campaign_id)
        .first()
    )
    if not pot:
        raise HTTPException(status_code=404, detail="Marmite non trouvée")

    return CampaignResponse(
        id=str(pot.id),
        # ✅ CORRIGÉ : recipe → product
        product=ProductSummary(
            id=pot.product.id,
            name=pot.product.name,
            category=pot.product.category,
            image_url=pot.product.image_url,
        ),
        target_date=pot.target_date,
        status=pot.status,
        minimum_orders=pot.minimum_orders,
        max_orders=pot.max_orders,
        current_orders=pot.current_orders,
        current_revenue=float(pot.current_revenue),
        preorder_price=float(pot.preorder_price),
        live_price=float(pot.live_price),
        sponsor_pack_price=float(pot.sponsor_pack_price),
        discount_percentage=float(pot.discount_percentage),
        display_price=float(pot.display_price),
        progress_percentage=float(pot.progress_percentage),
        remaining_to_fund=int(pot.remaining_to_fund),
        remaining_capacity=int(pot.remaining_capacity),
        remaining_amount=float(pot.remaining_amount),
        bonus_description=pot.bonus_description,
        is_funded=pot.is_funded,
        is_active=pot.is_active,
        funded_at=pot.funded_at,
        created_at=pot.created_at,
        updated_at=pot.updated_at,
    )


# ============================================================
# ⚙️ ENDPOINTS ADMIN (inchangés sauf import)
# ============================================================

@router.post("/", status_code=201)
def create_campaign(
    data: CampaignCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    product = db.query(Product).filter(Product.id == data.recipe_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    existing = db.query(CollectivePot).filter(
        CollectivePot.product_id == data.recipe_id,
        CollectivePot.target_date == data.target_date,
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Une marmite existe déjà pour {product.name} le {data.target_date}",
        )

    new_pot = CollectivePot(
        product_id=data.recipe_id,
        target_date=data.target_date,
        minimum_orders=data.minimum_orders,
        max_orders=data.max_orders,
        preorder_price=data.preorder_price,
        live_price=data.live_price,
        sponsor_pack_price=data.sponsor_pack_price,
        discount_percentage=data.discount_percentage,
        status=CollectivePotStatus.ACTIVE.value,
        bonus_description=data.bonus_description,
        admin_notes=data.admin_notes,
    )
    db.add(new_pot)
    db.commit()
    db.refresh(new_pot)

    logger.info(
        "🎯 CollectivePot créé : %s pour le %s (objectif %d portions)",
        product.name, data.target_date, data.minimum_orders,
    )
    return {
        "status": "success",
        "campaign_id": str(new_pot.id),
        "message": f"Marmite '{product.name}' lancée pour le {data.target_date}",
    }


@router.patch("/{campaign_id}/status")
def update_campaign_status(
    campaign_id: str,
    new_status: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    pot = db.query(CollectivePot).filter(CollectivePot.id == campaign_id).first()
    if not pot:
        raise HTTPException(status_code=404, detail="Marmite non trouvée")
    try:
        new_status_enum = CollectivePotStatus(new_status)
    except ValueError:
        valid_values = [s.value for s in CollectivePotStatus]
        raise HTTPException(status_code=400, detail=f"Statut invalide. Valeurs acceptées : {valid_values}")
    if not pot.can_transition_to(new_status_enum):
        raise HTTPException(status_code=400, detail=f"Transition invalide : {pot.status} → {new_status}")

    old_status = pot.status
    pot.status = new_status_enum.value
    pot.updated_at = datetime.utcnow()
    db.commit()
    logger.info("🔄 CollectivePot %s : %s → %s", pot.product.name if pot.product else "?", old_status, new_status)
    return {"status": "success", "campaign_id": campaign_id, "old_status": old_status, "new_status": new_status}


@router.delete("/{campaign_id}")
def cancel_campaign(
    campaign_id: str,
    reason: str = Query(...),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production")),
):
    pot = db.query(CollectivePot).filter(CollectivePot.id == campaign_id).first()
    if not pot:
        raise HTTPException(status_code=404, detail="Marmite non trouvée")
    if pot.current_orders > 0:
        raise HTTPException(status_code=400, detail=f"Impossible d'annuler : {pot.current_orders} clients ont déjà commandé")

    pot.status = CollectivePotStatus.CANCELLED.value
    pot.admin_notes = f"Annulée : {reason}"
    db.commit()
    logger.warning("🚫 CollectivePot annulé : %s - %s", pot.product.name if pot.product else "?", reason)
    return {"status": "success", "message": "Marmite annulée"}