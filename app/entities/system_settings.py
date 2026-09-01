# app/entities/system_settings.py
"""
Paramètres globaux du système KemTchop.
Ces valeurs servent de défaut lors de la création des DailyOffers.
"""

from sqlalchemy import Column, Integer, String, Time
from app.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, default=1)
    
    # Heures de cutoff (valeurs par défaut)
    reservation_cutoff_time = Column(Time, nullable=False, default="19:30:00",
                                      comment="Heure limite de réservation (veille)")
    order_cutoff_time = Column(Time, nullable=False, default="14:00:00",
                                comment="Heure limite de commande J+0")
    
    # Horizon de réservation
    max_reservation_days = Column(Integer, nullable=False, default=7,
                                   comment="Nombre maximum de jours à l'avance pour réserver")
    
    # Métadonnées
    updated_at = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)