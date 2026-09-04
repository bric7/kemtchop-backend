from sqlalchemy import text
from app.database import engine

def update():
    # URLs Cloudinary MP4 distinctes
    video_7 = "https://res.cloudinary.com/dqk85euoh/video/upload/kemtchop/videos/uw6uplofubxuqbr3kgr6.mp4"
    video_8 = "https://res.cloudinary.com/dqk85euoh/video/upload/kemtchop/videos/ruyrhgf3ooldjdjwgf2c.mp4"

    with engine.connect() as conn:
        print(f"🚀 Mise à jour des vidéos distinctes...")

        # Produit 7 (Okok)
        conn.execute(text(f"UPDATE products SET video_url='{video_7}' WHERE id=7"))
        conn.execute(text(f"UPDATE daily_offers SET video_url='{video_7}' WHERE product_id=7"))
        conn.execute(text(f"UPDATE reels SET video_url='{video_7}' WHERE product_name='Okok'"))

        # Produit 8 (Sanga)
        conn.execute(text(f"UPDATE products SET video_url='{video_8}' WHERE id=8"))
        conn.execute(text(f"UPDATE daily_offers SET video_url='{video_8}' WHERE product_id=8"))
        conn.execute(text(f"UPDATE reels SET video_url='{video_8}' WHERE product_name='Sanga'"))

        conn.commit()
        print("✅ Base Neon mise à jour avec des vidéos distinctes pour 7 et 8.")

if __name__ == "__main__":
    update()
