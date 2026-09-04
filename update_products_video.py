from sqlalchemy import text
from app.database import engine

def update():
    with engine.connect() as conn:
        conn.execute(text("UPDATE products SET video_url='https://res.cloudinary.com/dmc123/video/upload/v1/kemtchop/videos/demo_okok' WHERE id=7"))
        conn.execute(text("UPDATE products SET video_url='https://res.cloudinary.com/dmc123/video/upload/v1/kemtchop/videos/demo_sanga' WHERE id=8"))
        conn.commit()
        print("✅ Products 7 and 8 updated with demo videos.")

if __name__ == "__main__":
    update()
