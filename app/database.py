# app/database.py - Version stable pour Railway
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Style SQLAlchemy 2.0
class Base(DeclarativeBase):
    pass

# 1. Lire l'URL depuis les variables d'environnement
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # ✅ Ne pas crasher à l'import, mais lever une erreur explicite au premier usage
    DATABASE_URL = "sqlite:///./dev-fallback.db"  # Fallback temporaire pour dev
    print("⚠️  WARNING: DATABASE_URL not set. Using SQLite fallback.")

# 2. Créer le moteur (ne connecte PAS immédiatement)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,          # ✅ Vérifie la connexion avant chaque requête
    pool_recycle=3600,           # ✅ Recycle les connexions après 1h (évite les timeouts Neon)
    echo=False                   # ✅ Mettre True pour debug SQL
)

# 3. Créer la factory de sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Fonction de dépendance FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()