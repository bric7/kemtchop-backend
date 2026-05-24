# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool


# Récupère l'URL depuis les variables d'environnement
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    # Fallback pour le dev local (à remplacer par ta vraie URL Neon)
    SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Ajoute sslmode=require si manquant (Neon l'exige)
if "sslmode" not in SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL += "sslmode=require"

# Création du moteur avec NullPool pour Neon (serverless)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,          # Attendre 30s pour obtenir une connexion
    pool_recycle=1800,        # Recycler après 30 min
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 30,
        "options": "-c statement_timeout=60000"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()