# app/routes/settings.py
# ============================================================
# ⚙️ ROUTES PARAMÈTRES SYSTÈME - KemTchop API
# ============================================================

import logging
from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities.system_settings import SystemSettings
from app.auth import get_current_user

logger = logging.getLogger("kemtchop.settings")
router = APIRouter(prefix="/settings", tags=["Settings"])


# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
class SystemSettingsResponse(BaseModel):
    reservation_cutoff_time: str  # Format "HH:MM"
    order_cutoff_time: str        # Format "HH:MM"
    max_reservation_days: int
    model_config = ConfigDict(from_attributes=True)


class SystemSettingsUpdate(BaseModel):
    reservation_cutoff_time: Optional[str] = None  # Format "HH:MM"
    order_cutoff_time: Optional[str] = None        # Format "HH:MM"
    max_reservation_days: Optional[int] = None


# ============================================================
# 🔧 HELPERS
# ============================================================
def get_or_create_settings(db: Session) -> SystemSettings:
    """Récupère les paramètres système, ou crée les valeurs par défaut si absents."""
    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings:
        settings = SystemSettings(
            id=1,
            reservation_cutoff_time=time(19, 30),
            order_cutoff_time=time(14, 0),
            max_reservation_days=7,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def parse_time_string(time_str: str) -> time:
    """Parse une chaîne 'HH:MM' en objet time."""
    try:
        parts = time_str.strip().split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=f"Format d'heure invalide: '{time_str}'. Utilisez 'HH:MM'.")


# ============================================================
# 📱 ENDPOINTS PUBLICS (Lecture seule)
# ============================================================
@router.get("/system", response_model=SystemSettingsResponse)
def get_system_settings(db: Session = Depends(get_db)):
    """Récupère les paramètres système actuels (cutoffs, horizon)."""
    settings = get_or_create_settings(db)
    return SystemSettingsResponse(
        reservation_cutoff_time=settings.reservation_cutoff_time.strftime("%H:%M"),
        order_cutoff_time=settings.order_cutoff_time.strftime("%H:%M"),
        max_reservation_days=settings.max_reservation_days,
    )


# ============================================================
# 👑 ENDPOINTS ADMIN (Modification)
# ============================================================
@router.put("/system", response_model=SystemSettingsResponse)
def update_system_settings(
    data: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Admin : Modifie les paramètres système (cutoffs, horizon)."""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")

    settings = get_or_create_settings(db)

    if data.reservation_cutoff_time is not None:
        settings.reservation_cutoff_time = parse_time_string(data.reservation_cutoff_time)

    if data.order_cutoff_time is not None:
        settings.order_cutoff_time = parse_time_string(data.order_cutoff_time)

    if data.max_reservation_days is not None:
        if data.max_reservation_days < 1 or data.max_reservation_days > 30:
            raise HTTPException(status_code=400, detail="max_reservation_days doit être entre 1 et 30")
        settings.max_reservation_days = data.max_reservation_days

    from app.utils.timezone import get_business_datetime
    settings.updated_at = get_business_datetime().isoformat()
    settings.updated_by = current_user.get("name", "admin")

    db.commit()
    db.refresh(settings)

    logger.info(f"⚙️ Paramètres système mis à jour par {settings.updated_by}")

    return SystemSettingsResponse(
        reservation_cutoff_time=settings.reservation_cutoff_time.strftime("%H:%M"),
        order_cutoff_time=settings.order_cutoff_time.strftime("%H:%M"),
        max_reservation_days=settings.max_reservation_days,
    )