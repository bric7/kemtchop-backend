import uuid
from datetime import date, timedelta
from app.database import SessionLocal
from app.entities import Product, CollectivePot, User
from app.enums import CollectivePotStatus
from app.auth import get_password_hash

def seed():
    db = SessionLocal()
    try:
        # 1. Admin User
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@kemtchop.com",
                hashed_password=get_password_hash("adminpassword"),
                role="admin",
                is_active=True,
                full_name="Admin Tchopiol",
                phone="+237600000000",
                permissions=["manage_production", "manage_orders", "manage_users"]
            )
            db.add(admin)
            print("Admin created")

        # 2. Product
        product = db.query(Product).filter(Product.name == "Eru & Waterfufu").first()
        if not product:
            product = Product(
                name="Eru & Waterfufu",
                category="Traditionnel",
                description="Le meilleur Eru du Mboa",
                price=2500.0,
                image_url="https://res.cloudinary.com/demo/image/upload/v1/tchopiol/eru.jpg"
            )
            db.add(product)
            db.flush()
            print("Product created")

        # 3. Campaign (Tomorrow)
        tomorrow = date.today() + timedelta(days=1)
        pot = db.query(CollectivePot).filter(CollectivePot.target_date == tomorrow).first()
        if not pot:
            pot = CollectivePot(
                id=uuid.uuid4(),
                product_id=product.id,
                target_date=tomorrow,
                minimum_orders=10,
                max_orders=50,
                current_orders=0,
                preorder_price=2000.0,
                live_price=2500.0,
                sponsor_pack_price=15000.0,
                discount_percentage=20.0,
                status=CollectivePotStatus.ACTIVE.value,
                bonus_description="Un piment offert par portion"
            )
            db.add(pot)
            print("Campaign created for tomorrow")

        db.commit()
        print("Seed completed successfully!")
    except Exception as e:
        print(f"Error seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
