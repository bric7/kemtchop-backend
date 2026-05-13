# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool  # Important pour Neon

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
    poolclass=NullPool,
    pool_pre_ping=True  # Vérifie la connexion avant chaque requête
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()