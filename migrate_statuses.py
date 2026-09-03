import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Charger les variables d'environnement si un fichier .env existe
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./dev-fallback.db"

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Migrating order statuses to uppercase...")
        result = conn.execute(text("UPDATE orders SET status = UPPER(status);"))
        conn.commit()
        print(f"Migration complete. {result.rowcount} orders updated.")

if __name__ == "__main__":
    migrate()
