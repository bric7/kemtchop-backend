from sqlalchemy import text
from app.database import engine

def update():
    # URLs réelles basées sur le cloud_name 'dqk85euoh'
    video_okok = "https://res.cloudinary.com/dqk85euoh/video/upload/v1/kemtchop/videos/okok.mp4"
    video_sanga = "https://res.cloudinary.com/dqk85euoh/video/upload/v1/kemtchop/videos/sanga.mp4"

    with engine.connect() as conn:
        print("🚀 Mise à jour des vidéos (account: dqk85euoh)...")

        # Produits
        conn.execute(text(f"UPDATE products SET video_url='{video_okok}' WHERE id=7"))
        conn.execute(text(f"UPDATE products SET video_url='{video_sanga}' WHERE id=8"))

        # Offres Quotidiennes
        conn.execute(text(f"UPDATE daily_offers SET video_url='{video_okok}' WHERE product_id=7"))
        conn.execute(text(f"UPDATE daily_offers SET video_url='{video_sanga}' WHERE product_id=8"))

        # Reels
        conn.execute(text(f"UPDATE reels SET video_url='{video_okok}' WHERE product_name='Okok'"))
        conn.execute(text(f"UPDATE reels SET video_url='{video_sanga}' WHERE product_name='Sanga'"))

        conn.commit()
        print("✅ Base Neon mise à jour (Products, DailyOffers, Reels).")

if __name__ == "__main__":
    update()
