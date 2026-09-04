from sqlalchemy import text
from app.database import engine

def update():
    # Utilisation de liens Cloudinary avec extension .mp4 pour garantir la compatibilité mobile
    video_okok = "https://res.cloudinary.com/demo/video/upload/q_auto,f_auto/dog.mp4" # Exemple valide
    video_sanga = "https://res.cloudinary.com/demo/video/upload/q_auto,f_auto/elephants.mp4" # Exemple valide

    with engine.connect() as conn:
        conn.execute(text(f"UPDATE products SET video_url='{video_okok}' WHERE id=7"))
        conn.execute(text(f"UPDATE products SET video_url='{video_sanga}' WHERE id=8"))
        # On met aussi à jour les reels existants car ils ont été créés par sync_reels
        conn.execute(text(f"UPDATE reels SET video_url='{video_okok}' WHERE product_name='Okok'"))
        conn.execute(text(f"UPDATE reels SET video_url='{video_sanga}' WHERE product_name='Sanga'"))
        conn.commit()
        print("✅ Products and Reels 7/8 updated with functional MP4 links.")

if __name__ == "__main__":
    update()
