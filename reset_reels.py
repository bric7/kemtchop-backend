from app.database import engine
from app.models import Base
from sqlalchemy import text

def reset():
    with engine.connect() as conn:
        print("Suppression de l'ancienne table reels...")
        conn.execute(text("DROP TABLE IF EXISTS reels CASCADE;"))
        conn.commit()
        print("Table supprimée.")

    print("Création de la nouvelle table avec les bonnes colonnes...")
    Base.metadata.create_all(bind=engine)
    print("Succès ! La table reels est toute neuve.")

if __name__ == "__main__":
    reset()