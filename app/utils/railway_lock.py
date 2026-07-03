# app/utils/railway_lock.py
import os
import logging
from sqlalchemy import create_engine, text
from app.database import SessionLocal

logger = logging.getLogger("kemtchop.railway_lock")

def acquire_orchestrator_lock() -> bool:
    """
    ✅ Évite que l'orchestrateur tourne sur plusieurs replicas Railway.
    
    Stratégie : Utilise RAILWAY_REPLICA_ID (défini par Railway) pour élire un leader.
    Si la variable n'existe pas (dev local), on exécute normalement.
    """
    replica_id = os.getenv("RAILWAY_REPLICA_ID")
    
    # Dev local : pas de lock nécessaire
    if replica_id is None:
        logger.info("[LOCK] Mode local : orchestrateur actif")
        return True
    
    # Production : seul le replica "0" exécute l'orchestrateur
    if replica_id == "0":
        logger.info("[LOCK] Replica leader (ID=%s) : orchestrateur actif", replica_id)
        return True
    else:
        logger.info("[LOCK] Replica follower (ID=%s) : orchestrateur en standby", replica_id)
        return False

# Alternative avancée : lock via base de données (si tu veux un failover)
def acquire_db_lock(db_session, lock_name: str = "orchestrator", ttl_seconds: int = 60) -> bool:
    """
    Lock distribué via PostgreSQL (pg_advisory_lock).
    Plus robuste mais nécessite une connexion DB.
    """
    try:
        result = db_session.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": hash(lock_name) % (2**31)}  # Clé 32-bit pour pg_advisory_lock
        ).scalar()
        if result:
            # Programmer le unlock automatique après TTL
            db_session.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": hash(lock_name) % (2**31)}
            )
            logger.info("[DB_LOCK] Lock acquis pour %s", lock_name)
            return True
        logger.warning("[DB_LOCK] Lock déjà détenu par une autre instance")
        return False
    except Exception as e:
        logger.error("[DB_LOCK] Erreur acquisition lock : %s", e)
        return False  # Fail-safe : ne pas exécuter si lock échoue