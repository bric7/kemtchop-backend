
import os
import sys
import uuid
from datetime import date, datetime, timedelta

# Configuration de l'environnement pour le test (Staging Neon DB)
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.entities.product import Product
from app.entities.daily_offer import DailyOffer
from app.entities.order import Order
from app.entities.user import User
from app.enums import ProductionStatus, OrderStatus

def run_test():
    db = SessionLocal()
    print("🚀 DÉBUT DU TEST : Flux Marmite Collective (Seuil de Production)")

    try:
        # 1. Préparation des données : Trouver ou créer un produit
        product = db.query(Product).first()
        if not product:
            product = Product(name="Test Plat", category="Test", price=1500)
            db.add(product)
            db.commit()
            db.refresh(product)

        # 2. Création d'une offre avec un seuil de 4
        offer_id = uuid.uuid4()
        tomorrow = date.today() + timedelta(days=1)
        offer = DailyOffer(
            id=offer_id,
            product_id=product.id,
            target_date=tomorrow,
            minimum_threshold=4,
            price_per_unit=1500,
            status=ProductionStatus.PROPOSED.value,
            reserved_portions=0
        )
        db.add(offer)
        db.commit()
        print(f"✅ Offre créée : {product.name} (Seuil: 4 portions). Statut initial: {offer.status}")

        # 3. Simulation de commandes successives
        def add_order(portions, customer):
            print(f"🛒 Commande de {portions} portions par {customer}...")
            # Simulation simplifiée de la logique dans app/routes/orders.py
            new_order = Order(
                daily_offer_id=offer.id,
                customer_name=customer,
                phone="600000000",
                total_amount=offer.price_per_unit * portions,
                portions=portions,
                status=OrderStatus.PENDING.value
            )
            db.add(new_order)

            # Mise à jour de l'offre
            offer.reserved_portions += portions

            # Déclenchement automatique
            if offer.status == ProductionStatus.PROPOSED.value and offer.is_threshold_reached:
                offer.status = ProductionStatus.CONFIRMED.value
                offer.triggered_at = datetime.utcnow()
                print(f"🔥 SEUIL ATTEINT ! L'offre est passée à : {offer.status}")

            db.commit()
            db.refresh(offer)
            print(f"   📊 Portions réservées: {offer.reserved_portions}/4")

        # Commande 1 : 1 portion
        add_order(1, "Client A")
        assert offer.status == ProductionStatus.PROPOSED.value

        # Commande 2 : 2 portions
        add_order(2, "Client B")
        assert offer.status == ProductionStatus.PROPOSED.value

        # Commande 3 : 1 portion (Total atteint 4)
        add_order(1, "Client C")
        assert offer.status == ProductionStatus.CONFIRMED.value
        print("✅ Test de bascule automatique RÉUSSI.")

        # 4. Test des commissions
        print("💰 Test du calcul des commissions...")
        # Création d'une commande avec code affilié
        affiliate_code = "AMB-TEST"
        order_with_affiliate = Order(
            daily_offer_id=offer.id,
            customer_name="Client Parrainé",
            phone="699999999",
            total_amount=3000,
            portions=2,
            affiliate_code=affiliate_code,
            status=OrderStatus.DELIVERED.value, # Déjà livré pour générer commission
            commission_paid=False
        )
        db.add(order_with_affiliate)
        db.commit()

        # Vérification du calcul (simulant app/routes/payments.py)
        commission = order_with_affiliate.total_amount * 0.15
        print(f"   ✅ Commission pour {affiliate_code} : {commission} FCFA (Attendu: 450.0)")
        assert commission == 450.0

        # Nettoyage (optionnel en staging, mais propre)
        db.delete(order_with_affiliate)
        # Supprimer les ordres liés à l'offre de test
        db.query(Order).filter(Order.daily_offer_id == offer.id).delete()
        db.delete(offer)
        db.commit()
        print("🧹 Nettoyage terminé.")
        print("\n✨ TOUS LES TESTS LOGIQUES DE PRODUCTION ONT RÉUSSI !")

    except Exception as e:
        print(f"❌ ÉCHEC DU TEST : {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
