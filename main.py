# app/main.py
# ============================================================
# 🍲 KEMTCHOP - Backend API (FastAPI) - ENTRY POINT
# ============================================================

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from sqlalchemy.orm import Session

from app.database import engine, get_db, SessionLocal
from app.database import Base
from app.auth import router as auth_router
from app.routes import daily_menu

# Import des routers modulaires
from app.routes import users, admin, orders, payments

# ============================================================
# 📦 ENVIRONMENT VARIABLES
# ============================================================
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("❌ SECRET_KEY non définie. Définis-la dans tes variables d'environnement.")

ALGORITHM = "HS256"
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")
if not ADMIN_SECRET_KEY:
    raise RuntimeError("❌ ADMIN_SECRET_KEY non définie. Définis-la dans tes variables d'environnement.")

# ============================================================
# 🪵 LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

# ============================================================
# 🌐 CONFIGURATION GLOBALE
# ============================================================
def get_local_ip() -> str:
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 8))
            return s.getsockname()[0]
    except:
        return "localhost"

SERVER_IP = os.getenv("SERVER_IP", "localhost")
BASE_URL = os.getenv("BASE_URL", f"http://{SERVER_IP}:8000")
LOCAL_IP = get_local_ip()
CLOUDFLARE_DOMAIN = os.getenv("CLOUDFLARE_DOMAIN", "https://tchopiol-production.up.railway.app")
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", f"{CLOUDFLARE_DOMAIN}/videos")

# ============================================================
# 🔐 CORS - Sécurisé
# ============================================================
DEFAULT_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:3000,"
    "http://localhost:8081,"
    "http://127.0.0.1:8081,"
    "exp://*,"
    "https://*.expo.dev,"
    "https://kemtchop-admin-96my.vercel.app"
)

ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv(
    "ALLOWED_ORIGINS", 
    DEFAULT_ORIGINS
).split(",") if origin.strip()]

# ============================================================
# 🚀 INITIALISATION FASTAPI
# ============================================================
app = FastAPI(
    title="KemTchop API",
    description="API de précommande de nourriture traditionnelle camerounaise",
    version="1.0.0",
    redirect_slashes=False
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 🛡️ RATE LIMITING
# ============================================================
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Trop de requêtes. Veuillez réessayer plus tard.", "retry_after": str(exc)},
    )

# ============================================================
# 📁 FICHIERS STATIQUES
# ============================================================
import os.path
script_dir = os.path.dirname(os.path.abspath(__file__))
videos_path = os.path.join(script_dir, "videos")
os.makedirs(videos_path, exist_ok=True)
app.mount("/videos", StaticFiles(directory=videos_path), name="videos")

# ============================================================
# 🔄 INCLUSION DES ROUTERS MODULAIRES
# ============================================================
app.include_router(auth_router)  # Auth existant
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(daily_menu.router)
# ============================================================
# 🏁 HEALTH CHECK & STARTUP
# ============================================================
@app.get("/health")
@limiter.limit("100 per minute")
def health_check(request: Request):
    return {"status": "ok", "service": "KemTchop API", "timestamp": datetime.utcnow().isoformat()}

@app.on_event("startup")
def on_startup():
    is_dev = os.getenv("EXPO_PUBLIC_ENV") != "production"
    if is_dev:
        logger.info("🔧 Mode développement : création des tables si nécessaire")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("🚀 Mode production : les migrations doivent être gérées via Alembic")
    logger.info("🚀 KemTchop API démarrée avec succès - toutes les routes admin sont protégées 🔐")

# ============================================================
# 🐍 LAMBDA HANDLER (serverless)
# ============================================================
from mangum import Mangum
handler = Mangum(app, lifespan="auto")