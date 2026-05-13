def init_db():
    from app.database import engine, Base
    from app.models import Base
    Base.metadata.create_all(bind=engine)