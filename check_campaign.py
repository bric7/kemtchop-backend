from app.database import SessionLocal
from app.entities.collective_pot import CollectivePot
from app.entities.product import Product
from datetime import date, timedelta

def check():
    db = SessionLocal()
    try:
        print("--- Vérification de la Campagne ---")
        campaigns = db.query(CollectivePot).all()
        if not campaigns:
            print("Aucune campagne trouvée.")
            return

        for pot in campaigns:
            product = db.query(Product).filter(Product.id == pot.product_id).first()
            prod_name = product.name if product else "Inconnu"
            print(f"ID: {pot.id}")
            print(f"Produit: {prod_name}")
            print(f"Date: {pot.target_date}")
            print(f"Statut: {pot.status}")
            print(f"Prix Live: {pot.live_price}")
            print("-" * 30)

    finally:
        db.close()

if __name__ == "__main__":
    check()
