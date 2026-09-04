import os
from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        print("Migrating daily_offers...")
        conn.execute(text("ALTER TABLE daily_offers ADD COLUMN IF NOT EXISTS video_url VARCHAR(500)"))
        conn.execute(text("ALTER TABLE daily_offers ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)"))
        conn.commit()
        print("✅ Migration successful!")

if __name__ == "__main__":
    migrate()
