# main.py - VERSION SIMPLIFIÉE ET FONCTIONNELLE
# ============================================================
# 🍲 KEMTCHOP - Backend API - ENTRY POINT (Simplifié)
# ============================================================

import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 📦 ENV & LOGGING
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

# ✅ Validation des secrets
for key in ["SECRET_KEY", "ADMIN_SECRET_KEY"]:
    if not os.getenv(key):
        raise RuntimeError(f"❌ {key} non définie")

# 🗄️ DATABASE IMPORTS
from app.database import engine, Base, SessionLocal

# 🌐 CONFIG RÉSEAU
def get_local_ip() -> str:
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 8))
            return s.getsockname()[0]
    except:
        return "localhost"

BASE_URL = os.getenv("BASE_URL", f"http://{get_local_ip()}:8000")
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", f"{os.getenv('CLOUDFLARE_DOMAIN', BASE_URL)}/videos")

# 🔐 CORS
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8081,exp://*,https://*.expo.dev"
).split(",") if o.strip()]

# ============================================================
# 🚀 FASTAPI APP
# ============================================================
app = FastAPI(
    title="KemTchop API",
    description="API de précommande culinaire",
    version="1.0.0",
    redirect_slashes=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Trop de requêtes. Veuillez réessayer plus tard."}
    )

# ============================================================
# 📁 FICHIERS STATIQUES
# ============================================================
videos_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos")
os.makedirs(videos_path, exist_ok=True)
app.mount("/videos", StaticFiles(directory=videos_path), name="videos")

# ============================================================
# 🔄 ROUTERS (imports modulaires)
# ============================================================
from app.auth import router as auth_router
from app.routes import users, admin, orders, payments, daily_menu

app.include_router(auth_router)
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(daily_menu.router, prefix="/daily-menu", tags=["Daily Menu"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

# ============================================================
# 🏁 HEALTH CHECK
# ============================================================
@app.get("/health")
@limiter.limit("100/minute")
def health_check(request: Request):
    return {
        "status": "ok",
        "service": "KemTchop API",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================
# ⚙️ STARTUP (version simplifiée)
# ============================================================
@app.on_event("startup")
def on_startup():
    is_dev = os.getenv("EXPO_PUBLIC_ENV") != "production"
    if is_dev:
        logger.info("🔧 Mode dev : création des tables si nécessaire")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("🚀 Mode prod : migrations via Alembic")
    logger.info("🚀 API KemTchop démarrée")

# ============================================================
# 🐍 SERVERLESS (Mangum)
# ============================================================
handler = Mangum(app, lifespan="off")
