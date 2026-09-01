# main.py
# KEMTCHOP Backend API v2.0 - Architecture CollectivePot
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routes.settings import router as settings_router

from app.config import settings
from app.database import engine, Base
from app.routes import dashboard, products, upload, reels, users, admin, orders, payments, daily_offers, suggestions
from app.auth import router as auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    is_dev = settings.ENV != "production"
    if is_dev:
        logger.info("Dev mode: creating tables")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("Prod mode: migrations via Alembic")
    logger.info(f"{settings.PROJECT_NAME} started")

    yield

    # Shutdown
    logger.info(f"{settings.PROJECT_NAME} shutting down")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    redirect_slashes=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

uploads_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

# ROUTERS
app.include_router(auth_router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(upload.router)
app.include_router(reels.router)
app.include_router(users.router)
app.include_router(daily_offers.router)
app.include_router(suggestions.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(settings_router)
@app.get("/health")
@limiter.limit("100/minute")
def health_check(request: Request):
    return {"status": "ok", "service": settings.PROJECT_NAME, "timestamp": datetime.utcnow().isoformat()}

handler = Mangum(app, lifespan="off")
