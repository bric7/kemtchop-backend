# app/main.py
# ============================================================
# 🍲 KEMTCHOP - Backend API (FastAPI) - ENTRY POINT
# ============================================================

import logging
import os
import os.path
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 📦 chargement initial des variables d'environnement
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("❌ SECRET_KEY non définie. Définis-la dans tes variables d'environnement.")

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")
if not ADMIN_SECRET_KEY:
    raise RuntimeError("❌ ADMIN_SECRET_KEY non définie. Définis-la dans tes variables d'environnement.")

ALGORITHM = "HS256"

# 🪵 LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

# 🗄️ DATABASE & TABLES CONFIGURATION
from app.database import engine, Base
from app.models import Product, DailyMenu, Order, User  # Garantit le chargement complet de l'ORM

# ============================================================
# 🌐 CONFIGURATION RÉSEAU ET DOMAINES GLOBAUX
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
# 🔐 CONFIGURATION SÉCURISÉE DES CORS
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
# 🚀 INITIALISATION DE L'APPLICATION FASTAPI
# ============================================================
app = FastAPI(
    title="KemTchop API",
    description="API d'orchestration de production culinaire collective",
    version="1.1.0",
    redirect_slashes=False
)

# Application du Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 🛡️ SÉCURITÉ ET PROTECTION (RATE LIMITING)
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
# 📁 STORAGE DES FICHIERS STATIQUES (Vidéos Reels)
# ============================================================
script_dir = os.path.dirname(os.path.abspath(__file__))
videos_path = os.path.join(script_dir, "videos")
os.makedirs(videos_path, exist_ok=True)
app.mount("/videos", StaticFiles(directory=videos_path), name="videos")

# ============================================================
# 🔄 ARCHITECTURE ROUTERS : FLUX ET SECTEURS ÉTANCHES
# ============================================================
from app.auth import router as auth_router
from app.routes import users, admin, orders, payments, daily_menu

# --- UNIVERS COMPTE ET AUTHENTIFICATION ---
app.include_router(auth_router)
app.include_router(users.router, prefix="/users", tags=["Users"])

# --- UNIVERS CLIENT (MOBILE APP) ---
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(daily_menu.router)  # Contient l'endpoint mobile /daily-menu/tomorrow

# --- UNIVERS EXPÉRIENCE ET BACKOFFICE ADMIN ---
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])

# ============================================================
# 🏁 CONTRÔLE DE SANTÉ ET CYCLE DE VIE (STARTUP)
# ============================================================
@app.get("/health")
@limiter.limit("100 per minute")
def health_check(request: Request):
    return {
        "status": "ok", 
        "service": "KemTchop API", 
        "timestamp": datetime.utcnow().isoformat()
    }

@app.on_event("startup")
def on_startup():
    is_dev = os.getenv("EXPO_PUBLIC_ENV") != "production"
    if is_dev:
        logger.info("🔧 Mode développement détecté : génération automatique des tables ORM")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("🚀 Mode production actif : les structures de données dépendent d'Alembic")
    logger.info("🚀 API KEMTCHOP connectée avec succès au nouveau modèle DailyMenu 🔐")

# ============================================================
# 🐍 LAMBDA SERVERLESS INTERFACE (Mangum)
# ============================================================
handler = Mangum(app, lifespan="auto")