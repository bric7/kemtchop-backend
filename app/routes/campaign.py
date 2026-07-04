# app/routes/campaign.py
import logging
from datetime import date, timedelta, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.entities.campaign import Campaign
from app.entities.product import Product
from app.enums import CampaignStatus
from app.schemas.campaign import CampaignCreate, CampaignResponse, RecipeSummary
from app.auth import check_permission

logger = logging.getLogger("kemtchop.campaigns")

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


# ============================================================
# 📱 ENDPOINTS PUBLICS (Frontend Mobile)
# ============================================================

@router.get("/tomorrow", response_model=List[CampaignResponse])
def get_tomorrow_campaigns(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    funded_only: bool = Query(False, description="Retourner seulement les campaigns funded"),
    active_only: bool = Query(True, description="Retourner seulement les campaigns actives")
):
    """
    ✅ Récupère les campaigns pour demain (modèle Kickstarter)
    
    C'est L'ENDPOINT PRINCIPAL pour le frontend mobile.
    Il retourne toutes les "marmites à financer" pour demain.
    """
    tomorrow = date.today() + timedelta(days=1)
    
    # Query de base avec jointure sur Product (recipe)
    query = db.query(Campaign).options(joinedload(Campaign.recipe)).filter(
        Campaign.target_date == tomorrow
    )
    
    # Filtres de statut
    if active_only and not funded_only:
        query = query.filter(Campaign.status == CampaignStatus.ACTIVE.value)
    elif funded_only:
        query = query.filter(Campaign.status == CampaignStatus.FUNDED.value)
    else:
        # Actives + funded
        query = query.filter(
            Campaign.status.in_([
                CampaignStatus.ACTIVE.value,
                CampaignStatus.FUNDED.value
            ])
        )
    
    # Filtre par catégorie
    if category and category != "Tout":
        query = query.join(Product).filter(Product.category == category)
    
    campaigns = query.all()
    
    # ✅ Transformer en réponse avec les propriétés calculées
    result = []
    for campaign in campaigns:
        result.append(CampaignResponse(
            id=str(campaign.id),
            recipe=RecipeSummary(
                id=campaign.recipe.id,
                name=campaign.recipe.name,
                category=campaign.recipe.category,
                image_url=campaign.recipe.image_url,
    
            ),
            target_date=campaign.target_date,
            status=campaign.status,
            minimum_orders=campaign.minimum_orders,
            max_orders=campaign.max_orders,
            current_orders=campaign.current_orders,
            current_revenue=float(campaign.current_revenue),
            pack_price=float(campaign.pack_price),
            early_bird_price=float(campaign.early_bird_price),
            standard_price=float(campaign.standard_price),
            discount_percentage=float(campaign.discount_percentage),
            display_price=float(campaign.display_price),
            progress_percentage=float(campaign.progress_percentage),
            remaining_to_fund=int(campaign.remaining_to_fund),
            remaining_amount=float(campaign.remaining_amount),
            bonus_description=campaign.bonus_description,
            is_funded=campaign.is_funded,
            is_active=campaign.is_active,
            funded_at=campaign.funded_at,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at
        ))
    
    # Trier par progression décroissante (les plus proches du seuil en premier)
    result.sort(key=lambda x: x.progress_percentage, reverse=True)
    
    logger.info(f"📊 {len(result)} campaigns pour demain")
    return result


@router.get("/today", response_model=List[CampaignResponse])
def get_today_campaigns(db: Session = Depends(get_db)):
    """✅ Campaigns du jour (pour suivi en temps réel)"""
    today = date.today()
    
    campaigns = db.query(Campaign).options(joinedload(Campaign.recipe)).filter(
        Campaign.target_date == today,
        Campaign.status.in_([
            CampaignStatus.ACTIVE.value,
            CampaignStatus.FUNDED.value
        ])
    ).all()
    
    return [
        CampaignResponse(
            id=str(c.id),
            recipe=RecipeSummary(
                id=c.recipe.id,
                name=c.recipe.name,
                category=c.recipe.category,
                image_url=c.recipe.image_url,
                complements=c.recipe.complements
            ),
            target_date=c.target_date,
            status=c.status,
            minimum_orders=c.minimum_orders,
            max_orders=c.max_orders,
            current_orders=c.current_orders,
            current_revenue=float(c.current_revenue),
            pack_price=float(c.pack_price),
            early_bird_price=float(c.early_bird_price),
            standard_price=float(c.standard_price),
            display_price=float(c.display_price),
            progress_percentage=float(c.progress_percentage),
            remaining_to_fund=int(c.remaining_to_fund),
            bonus_description=c.bonus_description,
            is_funded=c.is_funded,
            is_active=c.is_active,
            funded_at=c.funded_at,
            created_at=c.created_at,
            updated_at=c.updated_at
        )
        for c in campaigns
    ]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign_detail(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """✅ Détail d'une Campaign spécifique"""
    campaign = db.query(Campaign).options(joinedload(Campaign.recipe)).filter(
        Campaign.id == campaign_id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign non trouvée")
    
    return CampaignResponse(
        id=str(campaign.id),
        recipe=RecipeSummary(
            id=campaign.recipe.id,
            name=campaign.recipe.name,
            category=campaign.recipe.category,
            image_url=campaign.recipe.image_url,
            complements=campaign.recipe.complements
        ),
        target_date=campaign.target_date,
        status=campaign.status,
        minimum_orders=campaign.minimum_orders,
        max_orders=campaign.max_orders,
        current_orders=campaign.current_orders,
        current_revenue=float(campaign.current_revenue),
        pack_price=float(campaign.pack_price),
        early_bird_price=float(campaign.early_bird_price),
        standard_price=float(campaign.standard_price),
        display_price=float(campaign.display_price),
        progress_percentage=float(campaign.progress_percentage),
        remaining_to_fund=int(campaign.remaining_to_fund),
        bonus_description=campaign.bonus_description,
        is_funded=campaign.is_funded,
        is_active=campaign.is_active,
        funded_at=campaign.funded_at,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at
    )


# ============================================================
# ⚙️ ENDPOINTS ADMIN (Gestion des Campaigns)
# ============================================================

@router.post("/", status_code=201)
def create_campaign(
    data: CampaignCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Créer une nouvelle Campaign (admin)"""
    # Vérifier que la recette existe
    recipe = db.query(Product).filter(Product.id == data.recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recette non trouvée")
    
    # Vérifier qu'il n'y a pas déjà une campaign pour cette recette/date
    existing = db.query(Campaign).filter(
        Campaign.recipe_id == data.recipe_id,
        Campaign.target_date == data.target_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Une campaign existe déjà pour {recipe.name} le {data.target_date}"
        )
    
    # Créer la Campaign
    new_campaign = Campaign(
        recipe_id=data.recipe_id,
        target_date=data.target_date,
        minimum_orders=data.minimum_orders,
        max_orders=data.max_orders,
        pack_price=data.pack_price,
        early_bird_price=data.early_bird_price,
        standard_price=data.standard_price,
        status=CampaignStatus.ACTIVE.value,
        bonus_description=data.bonus_description,
        admin_notes=data.admin_notes
    )
    
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    
    logger.info(
        "🎯 Campaign créée : %s pour le %s (objectif %d portions)",
        recipe.name, data.target_date, data.minimum_orders
    )
    
    return {
        "status": "success",
        "campaign_id": str(new_campaign.id),
        "message": f"Campaign '{recipe.name}' lancée pour le {data.target_date}"
    }


@router.patch("/{campaign_id}/status")
def update_campaign_status(
    campaign_id: str,
    new_status: str,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Modifier le statut d'une Campaign (admin)"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign non trouvée")
    
    try:
        new_status_enum = CampaignStatus(new_status)
    except ValueError:
        valid_values = [s.value for s in CampaignStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Statut invalide. Valeurs acceptées : {valid_values}"
        )
    
    if not campaign.can_transition_to(new_status_enum):
        raise HTTPException(
            status_code=400,
            detail=f"Transition invalide : {campaign.status} → {new_status}"
        )
    
    old_status = campaign.status
    campaign.status = new_status_enum.value
    campaign.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(
        "🔄 Campaign %s : %s → %s",
        campaign.recipe.name if campaign.recipe else "?",
        old_status, new_status
    )
    
    return {
        "status": "success",
        "campaign_id": campaign_id,
        "old_status": old_status,
        "new_status": new_status
    }


@router.delete("/{campaign_id}")
def cancel_campaign(
    campaign_id: str,
    reason: str = Query(...),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("manage_production"))
):
    """✅ Annuler une Campaign (admin)"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign non trouvée")
    
    if campaign.current_orders > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible d'annuler : {campaign.current_orders} clients ont déjà commandé"
        )
    
    campaign.status = CampaignStatus.CANCELLED.value
    campaign.admin_notes = f"Annulée : {reason}"
    db.commit()
    
    logger.warning(
        "🚫 Campaign annulée : %s - %s",
        campaign.recipe.name if campaign.recipe else "?",
        reason
    )
    
    return {"status": "success", "message": "Campaign annulée"}