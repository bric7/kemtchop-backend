from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.entities import Reel
from app.database import Base

# On s'assure que les tables existent (au cas où)
Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    
    # On vérifie si on a déjà des données pour ne pas faire de doublons
    if db.query(Reel).count() > 0:
        print("La base de données contient déjà des vidéos. Annulation du seed.")
        return

    # Liste des plats de démo
    plats_demo = [
        Reel(
            title="Le meilleur Eru de Yaoundé",
            video_url="https://mon-storage.com/eru_video.mp4",
            product_name="Eru & Waterfufu",
            price=5000.0
        ),
        Reel(
            title="Poisson Braisé (Sole Royale)",
            video_url="https://mon-storage.com/poisson_video.mp4",
            product_name="Poisson Braisé",
            price=7000.0
        ),
        Reel(
            title="Taro Sauce Jaune authentique",
            video_url="https://mon-storage.com/taro_video.mp4",
            product_name="Taro Sauce Jaune",
            price=6000.0
        )
    ]

    try:
        db.add_all(plats_demo)
        db.commit()
        print("✅ Base de données Tchopiol remplie avec succès !")
    except Exception as e:
        print(f"❌ Erreur lors du remplissage : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()