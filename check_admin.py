import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.entities.user import User
from app.security import verify_password
import re

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def normalize_phone(phone: str) -> str:
    return re.sub(r'\D', '', phone)

def check():
    db = SessionLocal()
    try:
        print("--- Vérification des Admins ---")
        admins = db.query(User).filter(User.role == "admin").all()
        if not admins:
            print("Aucun admin trouvé dans la base.")
            return

        for admin in admins:
            print(f"ID: {admin.id}")
            print(f"Username: {admin.username}")
            print(f"Phone: {admin.phone}")
            print(f"Normalized Phone: {normalize_phone(admin.phone) if admin.phone else 'N/A'}")
            print(f"Customer Name: {admin.customer_name}")

            pwd_test = "adminpassword"
            match = verify_password(pwd_test, admin.hashed_password)
            print(f"Vérification mot de passe '{pwd_test}': {'✅ OK' if match else '❌ FAILED'}")
            print("-" * 30)

    finally:
        db.close()

if __name__ == "__main__":
    check()
