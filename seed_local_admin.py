from app.database import SessionLocal
from app.entities.user import User
from app.security import get_password_hash
from app.config import settings
import re

def seed():
    print(f"--- Seeding Admin in {settings.DATABASE_URL.split('@')[-1]} ---")
    db = SessionLocal()
    try:
        phone = "600000000"
        # Search for admin by phone or username
        admin = db.query(User).filter((User.phone == phone) | (User.username == "admin")).first()

        hashed = get_password_hash("adminpassword")

        if not admin:
            admin = User(
                username="admin",
                customer_name="Admin KemTchop",
                phone=phone,
                hashed_password=hashed,
                role="admin",
                is_active=True,
                permissions="admin,manage_users,manage_orders,manage_production"
            )
            db.add(admin)
            print(f"✅ Created new admin: {phone}")
        else:
            admin.phone = phone
            admin.username = "admin"
            admin.hashed_password = hashed
            admin.role = "admin"
            admin.is_active = True
            print(f"✅ Updated existing admin: {admin.username}")

        db.commit()
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
