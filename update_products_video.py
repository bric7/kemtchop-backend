from sqlalchemy import text
from app.database import engine

def update():
    # URL réelle et vérifiée par l'utilisateur
    video_url = "https://res.cloudinary.com/dqk85euoh/video/upload/kemtchop/videos/ri9pkouqk86i0vakhm4q.mp4"

    with engine.connect() as conn:
        print(f"🚀 Mise à jour des vidéos avec le lien réel : {video_url}")

        # Produits 7 (Okok) et 8 (Sanga)
        conn.execute(text(f"UPDATE products SET video_url='{video_url}' WHERE id IN (7, 8)"))

        # Offres Quotidiennes liées
        conn.execute(text(f"UPDATE daily_offers SET video_url='{video_url}' WHERE product_id IN (7, 8)"))

        # Table des Reels (pour la synchro immédiate)
        conn.execute(text(f"UPDATE reels SET video_url='{video_url}' WHERE product_name IN ('Okok', 'Sanga')"))

        conn.commit()
        print("✅ Base Neon mise à jour avec succès.")

if __name__ == "__main__":
    update()
