# migrate_cloudinary.py - VERSION CORRIGÉE
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def migrate_to_cloudinary():
    if not DATABASE_URL:
        print("❌ DATABASE_URL non définie")
        return
    
    engine = create_engine(DATABASE_URL)
    
    # ⚠️ REMPLACER par le VRAI nom de ta table (trouvé à l'étape 2)
    TABLE_NAME = "reels"  # ou "reel", "products", etc.
    
    with engine.connect() as conn:
        # Migration images
        result = conn.execute(text(f"""
            UPDATE {TABLE_NAME}
            SET image_url = REPLACE(
                image_url, 
                'https://tchopiol-production.up.railway.app/videos/videos/', 
                'https://res.cloudinary.com/dqk85euoh/image/upload/kemtchop/products/'
            )
            WHERE image_url LIKE '%tchopiol-production.up.railway.app%'
        """))
        print(f"✅ Images mises à jour: {result.rowcount}")
        
        # Migration vidéos
        result = conn.execute(text(f"""
            UPDATE {TABLE_NAME}
            SET video_url = REPLACE(
                video_url, 
                'https://tchopiol-production.up.railway.app/videos/videos/', 
                'https://res.cloudinary.com/dqk85euoh/video/upload/kemtchop/videos/'
            )
            WHERE video_url LIKE '%tchopiol-production.up.railway.app%'
        """))
        print(f"✅ Vidéos mises à jour: {result.rowcount}")
        
        conn.commit()
    
    print("🎉 Migration Cloudinary terminée !")

if __name__ == "__main__":
    migrate_to_cloudinary()