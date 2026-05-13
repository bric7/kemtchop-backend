from app.database import engine
from sqlalchemy import text

def fix():
    with engine.connect() as conn:
        print("Vérification de la table reels...")
        # Ajout des colonnes manquantes si elles n'existent pas
        try:
            conn.execute(text("ALTER TABLE reels ADD COLUMN image_url VARCHAR;"))
            print("Colonne image_url ajoutée !")
        except Exception:
            print("La colonne image_url existe peut-être déjà.")
            
        try:
            conn.execute(text("ALTER TABLE reels ADD COLUMN video_url VARCHAR;"))
            print("Colonne video_url ajoutée !")
        except Exception:
            print("La colonne video_url existe peut-être déjà.")
            
        conn.commit()
        print("Base de données synchronisée.")

if __name__ == "__main__":
    fix()