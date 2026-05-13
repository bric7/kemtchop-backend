# init_db.py - À exécuter une fois après déploiement
from app.database import engine, Base
from app import models  # Importe tous tes modèles

def init_neon_db():
    """Crée les tables dans Neon si elles n'existent pas"""
    print("🔧 Création des tables dans Neon...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées avec succès !")

if __name__ == "__main__":
    init_neon_db()