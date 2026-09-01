# app/utils/timezone.py
"""
Module centralisé pour la gestion du fuseau horaire métier.
Toutes les opérations temporelles du système KemTchop doivent utiliser ces fonctions.
Fuseau horaire : Africa/Douala (UTC+1)
"""

from datetime import datetime, date, time
from zoneinfo import ZoneInfo

# Fuseau horaire métier du Cameroun
BUSINESS_TZ = ZoneInfo("Africa/Douala")


def get_business_datetime() -> datetime:
    """
    Retourne la date et l'heure actuelles dans le fuseau horaire métier (Africa/Douala).
    
    Returns:
        datetime: Date et heure actuelles en Afrique/Douala
    """
    return datetime.now(BUSINESS_TZ)


def get_business_date() -> date:
    """
    Retourne la date actuelle dans le fuseau horaire métier (Africa/Douala).
    
    Returns:
        date: Date actuelle en Afrique/Douala
    """
    return get_business_datetime().date()


def get_business_time() -> time:
    """
    Retourne l'heure actuelle dans le fuseau horaire métier (Africa/Douala).
    
    Returns:
        time: Heure actuelle en Afrique/Douala
    """
    return get_business_datetime().timetz()


def to_business_tz(dt: datetime) -> datetime:
    """
    Convertit un datetime vers le fuseau horaire métier.
    
    Args:
        dt: datetime à convertir (naive ou aware)
    
    Returns:
        datetime: datetime converti en Africa/Douala
    """
    if dt.tzinfo is None:
        # Si naive, on assume UTC
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(BUSINESS_TZ)


def combine_business_datetime(d: date, t: time) -> datetime:
    """
    Combine une date et une heure en un datetime aware (Africa/Douala).
    
    Args:
        d: date
        t: time
    
    Returns:
        datetime: datetime aware en Africa/Douala
    """
    return datetime.combine(d, t, tzinfo=BUSINESS_TZ)