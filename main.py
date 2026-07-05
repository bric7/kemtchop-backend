# main.py
# KEMTCHOP Backend API v2.0 - Architecture CollectivePot
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routes import dashboard
from app.routes import products

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

for key in ["SECRET_KEY", "ADMIN_SECRET_KEY"]:
    if not os.getenv(key):
        raise RuntimeError(f"Missing {key}")

from app.database import engine, Base

def get_local_ip():
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 8))
            return s.getsockname()[0]
    except Exception:
        return "localhost"

BASE_URL = os.getenv("BASE_URL", f"http://{get_local_ip()}:8000")

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:8081,exp://*,https://*.expo.dev"
    ).split(",") if o.strip()
]

app = FastAPI(title="KemTchop API", version="2.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

videos_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos")
os.makedirs(videos_path, exist_ok=True)
app.mount("/videos", StaticFiles(directory=videos_path), name="videos")

# ROUTERS - Architecture définitive (PAS de daily_menu)
from app.auth import router as auth_router
from app.routes import users, admin, orders, payments, campaign, suggestions

app.include_router(auth_router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(campaign.router)
app.include_router(suggestions.router)
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/health")
@limiter.limit("100/minute")
def health_check(request: Request):
    return {"status": "ok", "service": "KemTchop API", "timestamp": datetime.utcnow().isoformat()}

@app.on_event("startup")
def on_startup():
    is_dev = os.getenv("EXPO_PUBLIC_ENV") != "production"
    if is_dev:
        logger.info("Dev mode: creating tables")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("Prod mode: migrations via Alembic")
    logger.info("KemTchop API started")

handler = Mangum(app, lifespan="off")