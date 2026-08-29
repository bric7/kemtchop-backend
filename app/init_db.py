def init_db():
    from app.database import engine, Base
    import app.entities  # Charge tous les modèles
    Base.metadata.create_all(bind=engine)
