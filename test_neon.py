# test_neon.py
import os
from dotenv import load_dotenv
from app.database import engine
from sqlalchemy import text

load_dotenv()

def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()
            print(f"✅ Connexion Neon réussie !")
            print(f"🗄️ PostgreSQL version : {version[0][:50]}...")
            return True
    except Exception as e:
        print(f"❌ Échec de connexion : {e}")
        return False

if __name__ == "__main__":
    test_connection()