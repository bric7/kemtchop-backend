import uuid
import logging
from app.database import SessionLocal
from app.entities.reel import Reel
from app.entities.product import Product
from app.entities.daily_offer import DailyOffer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_reels")

def sync_reels():
    db = SessionLocal()
    try:
        # 1. Trouver les produits avec vidéo
        products = db.query(Product).filter(Product.video_url != None).all()
        logger.info(f"🔍 Trouvé {len(products)} produits avec vidéo.")

        for p in products:
            # Vérifier si un Reel existe déjà pour ce produit (basé sur le nom ou video_url)
            # Puisque Reel n'a pas de product_id direct, on utilise product_name
            existing_reel = db.query(Reel).filter(
                (Reel.product_name == p.name) | (Reel.video_url == p.video_url)
            ).first()

            if not existing_reel:
                logger.info(f"➕ Création d'un Reel pour le produit: {p.name}")
                new_reel = Reel(
                    id=uuid.uuid4(),
                    title=p.name,
                    product_name=p.name,
                    video_url=p.video_url,
                    image_url=p.image_url,
                    category=p.category,
                    price=p.price,
                    is_active=True,
                    priority=0
                )
                db.add(new_reel)
            else:
                logger.info(f"✅ Reel existe déjà pour {p.name}")

        db.commit()
        logger.info("✨ Synchronisation terminée.")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la synchronisation : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_reels()
