import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.entities.user import User
from app.security import get_password_hash
import re

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed():
    db = SessionLocal()
    try:
        print("--- Création de l'Admin ---")
        # On vérifie si l'admin existe déjà par le téléphone normalisé
        phone = "600000000"
        admin = db.query(User).filter(User.phone == phone).first()

        if not admin:
            admin = User(
                username="admin",
                customer_name="Admin KemTchop",
                phone=phone,
                hashed_password=get_password_hash("adminpassword"),
                role="admin",
                is_active=True,
                permissions="admin,manage_users,manage_orders,manage_production"
            )
            db.add(admin)
            db.commit()
            print(f"✅ Admin créé avec succès (Phone: {phone})")
        else:
            print(f"ℹ️ L'admin avec le téléphone {phone} existe déjà.")
            # Mise à jour du mot de passe au cas où
            admin.hashed_password = get_password_hash("adminpassword")
            admin.role = "admin"
            db.commit()
            print("✅ Admin mis à jour.")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
