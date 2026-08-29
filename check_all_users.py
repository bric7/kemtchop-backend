import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check():
    db = SessionLocal()
    try:
        print("--- Liste de TOUS les utilisateurs (Raw SQL) ---")
        result = db.execute(text("SELECT id, customer_name, phone, role, username FROM users"))
        rows = result.fetchall()
        if not rows:
            print("Aucun utilisateur trouvé.")
            return

        for row in rows:
            print(f"ID: {row[0]} | Name: {row[1]} | Phone: {row[2]} | Role: {row[3]} | Username: {row[4]}")

    finally:
        db.close()

if __name__ == "__main__":
    check()
