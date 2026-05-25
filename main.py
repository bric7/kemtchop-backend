# ============================================================
# 🍲 KEMTCHOP - Backend API (FastAPI)
# Fichier: main.py - VERSION FINALE CORRIGÉE
# ============================================================

# ============================================================
# 1️⃣ IMPORTS STANDARDS
# ============================================================
import os
import uuid
import subprocess
import shutil
import json
import re
import random
import string
import logging
import secrets
import socket
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# ============================================================
# 🛡️ RATE LIMITING IMPORTS
# ============================================================
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ============================================================
# 🚀 FASTAPI IMPORTS (TOUS requis)
# ============================================================
from fastapi import FastAPI, Request, status, Depends, HTTPException, BackgroundTasks, File, Form, UploadFile, Query, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ============================================================
# 🗄️ DATABASE & PYDANTIC
# ============================================================
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, Field, field_validator

# ============================================================
# 🔐 AUTH & UTILS
# ============================================================
from passlib.context import CryptContext
import requests
from jose import jwt

# ============================================================
# 📦 ENVIRONMENT VARIABLES (CRUCIAL)
# ============================================================
from dotenv import load_dotenv
load_dotenv()  # ← Charge .env en local (Railway utilise ses propres vars)

# ============================================================
# 📁 IMPORTS LOCAUX (ton code)
# ============================================================
from app.database import engine, get_db, SessionLocal
import app.models as models
from app.models import Order, Reel, Transaction, DeliverySettings, PasswordResetToken, User
from app.services.campay import campay_service
from app.services.expo_push import ExpoPushService
from auth import get_current_user, get_admin_user, check_permission, router

# ============================================================
# 2️⃣ CONFIGURATION GLOBALE
# ============================================================

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

# Password hashing (DOIT MATCHER auth.py)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto", pbkdf2_sha256__default_rounds=29000)

# JWT config
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
ALGORITHM = "HS256"
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

if not ADMIN_SECRET_KEY:
    logger.warning("⚠️ ADMIN_SECRET_KEY non définie - mode développement uniquement")

# IP locale pour les médias
def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 8))
            return s.getsockname()[0]
    except:
        return "localhost"

SERVER_IP = os.getenv("SERVER_IP", "localhost")
BASE_URL = os.getenv("BASE_URL", f"http://{SERVER_IP}:8000")
LOCAL_IP = get_local_ip()
MEDIA_BASE_URL = f"http://{LOCAL_IP}:8000"

# CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:8081,http://127.0.0.1:8081,http://10.250.73.113:8081,exp://*,https://*.expo.dev"
).split(",")

# ✅ Initialiser FastAPI
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
# 🛡️ RATE LIMITING CONFIGURATION
# ============================================================

# Initialiser le limiter (stockage en mémoire pour Railway)
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
app.state.limiter = limiter

# Gestionnaire d'erreur personnalisé pour rate limit exceeded
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Trop de requêtes. Veuillez réessayer plus tard.",
            "retry_after": str(exc)
        },
    )

# Fichiers statiques
script_dir = os.path.dirname(os.path.abspath(__file__))
videos_path = os.path.join(script_dir, "videos")
os.makedirs(videos_path, exist_ok=True)
app.mount("/videos", StaticFiles(directory=videos_path), name="videos")

# Router d'authentification
app.include_router(router)

# ============================================================
# 3️⃣ UTILITAIRES
# ============================================================

def validate_cameroon_phone(phone: str) -> bool:
    clean = re.sub(r'\D', '', phone)
    return bool(re.match(r'^(237)?6[0-9]{8}$', clean))

def normalize_phone(phone: str) -> str:
    return re.sub(r'\D', '', phone)

def compress_video(input_path: str, output_path: str):
    try:
        command = [
            'ffmpeg', '-i', input_path,
            '-vcodec', 'libx264', '-crf', '28',
            '-preset', 'veryfast', '-acodec', 'aac', '-y', output_path
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            os.remove(input_path)
            logger.info(f"✅ Vidéo compressée : {output_path}")
    except Exception as e:
        logger.error(f"❌ Erreur compress_video : {e}")
        if os.path.exists(input_path):
            os.remove(input_path)

def generate_unique_code(phone: str) -> str:
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    return f"KEM-{phone[-4:]}-{letters}"

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ============================================================
# 4️⃣ SCHÉMAS PYDANTIC (définis UNE FOIS)
# ============================================================

# --- Utilisateurs ---
class UserResponse(BaseModel):
    id: int
    username: Optional[str] = None
    phone: Optional[str] = None
    customer_name: Optional[str] = None
    role: Optional[str] = None
    is_affiliate: Optional[bool] = False
    affiliate_code: Optional[str] = None
    pending_commissions: Optional[float] = 0.0
    class Config:
        from_attributes = True

class UserCreateRequest(BaseModel):
    """Pour créer un membre d'équipe (manager/cuisine/livreur)"""
    customer_name: str = Field(..., min_length=2, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    phone: str
    password: Optional[str] = Field(None, min_length=6)
    role: str = Field(default="manager", pattern="^(admin|manager|cuisine|livreur|customer)$")
    permissions: Optional[List[str]] = []
    
    @field_validator('password')
    @classmethod
    def password_required_if_username(cls, v, info):
        data = info.data
        if data.get('username') and not v:
            raise ValueError('Mot de passe requis quand un username est défini')
        return v

class UserUpdateRequest(BaseModel):
    """Pour modifier un utilisateur existant"""
    customer_name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = Field(None, pattern="^(admin|manager|cuisine|livreur|customer)$")
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

class TokenUpdateRequest(BaseModel):
    phone: str
    expo_token: str

# --- Commandes ---
class OrderCreate(BaseModel):
    customer_name: str
    product_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    portion_size: str
    delivery_date: str 
    delivery_time: str 
    complement: Optional[str] = None
    affiliate_code: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    product_name: str
    customer_name: str
    phone: str
    zone: str
    total_amount: float
    deposit_amount: float
    portion_size: str
    delivery_date: str
    delivery_time: str
    complement: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    affiliate_code: Optional[str] = None
    class Config:
        from_attributes = True

# --- Reels/Produits ---
class ReelResponse(BaseModel):
    id: int
    title: str
    video_url: Optional[str] = None
    image_url: str
    product_name: str
    price: float
    category: Optional[str] = "Tout"
    is_available: Optional[bool] = True
    complements: Optional[str] = None
    class Config:
        from_attributes = True

# --- Authentification ---
class UserAuth(BaseModel):
    phone: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    phone: str
    password: str
    class Config:
        from_attributes = True
        extra = "ignore"

# --- Paiements ---
class PaymentInitRequest(BaseModel):
    order_id: int
    amount: float
    phone: str
    description: Optional[str] = "Acompte KemTchop"

class PaymentInitResponse(BaseModel):
    success: bool
    payment_url: str
    reference: str
    deposit_amount: float
    balance_amount: float
    message: str

# --- Analytics ---
class AnalyticsEvent(BaseModel):
    phone: str = Field(..., min_length=9, max_length=15)
    event_type: str = Field(..., pattern="^(video_view|product_view|add_to_cart|checkout_start|checkout_abandon|order_completed|affiliate_click|search)$")
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    video_id: Optional[int] = None
    cart_value: Optional[float] = None
    affiliate_code: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = {}

class CampaignTarget(BaseModel):
    phone: str
    customer_name: Optional[str] = None
    last_event: str
    last_event_date: datetime
    product_interest: Optional[str] = None
    cart_value: Optional[float] = None
    total_events: int
    class Config:
        from_attributes = True

class PushCampaignRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    target: str = Field(default="all")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sound: Optional[str] = Field(default="default")
    class Config:
        from_attributes = True

# --- Autres ---
class DeliverySettingsUpdate(BaseModel):
    zones: List[str]
    price: int

class ActivateAffiliateRequest(BaseModel):
    phone: str

class AddressCreate(BaseModel):
    phone: str
    city: str
    neighborhood: str
    details: str
    label: str

# ============================================================
# 5️⃣ ROUTES UTILISATEURS (avec rate limiting)
# ============================================================

@app.post("/users/register")
@limiter.limit("10 per minute")  # ← Anti-spam registration
async def register(request: Request, register_data: RegisterRequest, db: Session = Depends(get_db)):
    name, phone, password = register_data.name, register_data.phone, register_data.password
    if not all([name, phone, password]):
        raise HTTPException(status_code=400, detail="Tous les champs sont obligatoires.")
    
    clean_phone = normalize_phone(phone)
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro camerounais invalide")
    
    if db.query(User).filter(User.phone == clean_phone).first():
        raise HTTPException(status_code=400, detail="Ce numéro existe déjà")
    
    try:
        hashed_password = pwd_context.hash(str(password)[:72])
        generated_code = f"{name[:3].upper()}-{str(uuid.uuid4())[:4].upper()}"
        new_user = User(
            customer_name=name, phone=clean_phone, hashed_password=hashed_password,
            is_affiliate=False, affiliate_code=generated_code, has_requested_affiliate=False
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"✅ Nouvel utilisateur : {clean_phone}")
        return {"status": "success", "message": "Client enregistré"}
    except Exception as e:
        db.rollback()
        logger.error(f"❌ ERREUR REGISTER : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne")

@app.post("/users/login")
@limiter.limit("5 per minute; 20 per hour")  # ← Anti brute force
async def login(request: Request, user_data: UserAuth, db: Session = Depends(get_db)):
    clean_phone = normalize_phone(user_data.phone)
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user or not pwd_context.verify(user_data.password, user.hashed_password):
        # 🔴 Log les échecs de login
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"🚨 Échec login pour '{clean_phone}' depuis {client_ip}")
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    logger.info(f"✅ Connexion : {user.phone}")
    return {
        "status": "success", "user_name": user.customer_name,
        "is_affiliate": user.is_affiliate, "affiliate_code": user.affiliate_code
    }

@app.post("/users/update-token")
@limiter.limit("30 per minute")
async def update_user_token(request: Request, data: TokenUpdateRequest, db: Session = Depends(get_db)):
    if not validate_cameroon_phone(data.phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    user.expo_push_token = data.expo_token
    db.commit()
    logger.info(f"🔔 Token Expo mis à jour pour {data.phone}")
    return {"status": "success", "message": "Token mis à jour"}

@app.post("/users/add-address")
@limiter.limit("20 per minute")
async def add_address(request: Request, address: AddressCreate, db: Session = Depends(get_db)):
    if not validate_cameroon_phone(address.phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    if not db.query(User).filter(User.phone == address.phone).first():
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    logger.info(f"📍 Nouvelle adresse pour {address.phone}")
    return {"status": "success", "message": "Adresse enregistrée"}

# --- Mots de passe ---
@app.post("/admin/generate-reset-link/{phone}")
@limiter.limit("10 per minute")  # ← Anti-abus reset links
def generate_reset_link(request: Request, phone: str, db: Session = Depends(get_db)):
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Client introuvable")
    
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=2)
    db.add(PasswordResetToken(token=token, phone=phone, expires_at=expires))
    db.commit()
    
    link = f"https://kemtchop.app/setup-password?token={token}"
    logger.info(f"🔗 Lien reset généré pour {phone}")
    return {"link": link}

@app.post("/users/complete-setup")
@limiter.limit("10 per minute")
def complete_setup(request: Request, token: str, new_password: str, db: Session = Depends(get_db)):
    db_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    if not db_token:
        raise HTTPException(status_code=400, detail="Lien expiré ou invalide")
    
    user = db.query(User).filter(User.phone == db_token.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.hashed_password = pwd_context.hash(new_password[:72])
    db_token.used = True
    db.commit()
    logger.info(f"✅ Mot de passe configuré pour {db_token.phone}")
    return {"message": "Mot de passe configuré !"}

@app.post("/users/reset-password")
@limiter.limit("10 per minute")
async def reset_password(request: Request, data: dict, db: Session = Depends(get_db)):
    phone, new_password, admin_token = data.get("phone"), data.get("new_password"), data.get("admin_token")
    if not admin_token or admin_token != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Non autorisé")
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.hashed_password = pwd_context.hash(new_password[:72])
    db.commit()
    logger.info(f"🔐 Mot de passe réinitialisé pour {phone}")
    return {"status": "success", "message": "Mot de passe mis à jour"}

# --- Statut & affiliation ---
@app.get("/users/status")
@limiter.limit("60 per minute")
async def get_user_status(request: Request, phone: str, db: Session = Depends(get_db)):
    clean_phone = re.sub(r"\D", "", phone)
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user:
        return {"exists": False, "needs_setup": True, "message": "User not found"}
    
    if not user.hashed_password or len(user.hashed_password.strip()) < 10:
        return {"exists": True, "needs_setup": True, "phone": user.phone, "message": "Mot de passe requis"}
    
    pending = 0.0
    if user.is_affiliate and user.affiliate_code:
        total_sales = db.query(func.sum(Order.total_amount)).filter(
            Order.affiliate_code == user.affiliate_code, Order.status == "termine"
        ).scalar() or 0
        pending = float(total_sales) * 0.15
    
    return {
        "exists": True, "needs_setup": False, "is_affiliate": user.is_affiliate,
        "affiliate_code": user.affiliate_code, "pending_commissions": pending, "user_name": user.customer_name
    }

@app.patch("/users/request-affiliate")
@limiter.limit("10 per minute")
async def request_affiliate(request: Request, phone: str, db: Session = Depends(get_db)):
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    user.has_requested_affiliate = True
    db.commit()
    logger.info(f"🤝 Demande affiliation : {phone}")
    return {"message": "Demande envoyée"}

# ============================================================
# 6️⃣ ROUTES ADMIN (avec rate limiting renforcé)
# ============================================================

# --- Login admin ---
@app.post("/admin/login")
@limiter.limit("5 per minute; 20 per hour")  # ← CRITIQUE: Anti brute force admin
async def admin_login(request: Request, credentials: dict, db: Session = Depends(get_db)):
    username, password = credentials.get("username"), credentials.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Identifiants requis")
    
    user = db.query(User).filter(User.username == username, User.role == "admin").first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        # 🔴 Log les tentatives échouées
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"🚨 Échec login admin pour '{username}' depuis {client_ip}")
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    token = create_access_token(data={"sub": user.username, "role": user.role})
    logger.info(f"✅ Admin login: {username}")
    return {
        "token": token, "token_type": "bearer", "username": user.username,
        "role": user.role, "permissions": user.permissions.split(",") if user.permissions else []
    }

# --- Activation affilié ---
@app.post("/admin/activate-affiliate")
@limiter.limit("10 per minute")
async def activate_affiliate(request: Request, activate_request: ActivateAffiliateRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    phone = activate_request.phone
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(User).filter(User.phone == phone, User.role != "admin").first()
    if not user:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    
    if not user.is_affiliate:
        try:
            user.affiliate_code = generate_unique_code(phone)
            user.is_affiliate = True
            db.commit()
            db.refresh(user)
            logger.info(f"🎉 Affilié activé : {user.customer_name} ({user.affiliate_code})")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur activation : {e}")
            raise HTTPException(status_code=500, detail="Erreur lors de l'activation")
    
    return {
        "status": "success", "user_id": user.id, "user_name": user.customer_name,
        "phone": user.phone, "affiliate_code": user.affiliate_code,
        "share_link": f"{BASE_URL}/home?ref={user.affiliate_code}"
    }

# --- Gestion équipe : GET tous les utilisateurs ---
@app.get("/admin/users", response_model=List[UserResponse])
@limiter.limit("60 per minute")  # ← Lecture: plus permissif
def get_all_users(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(check_permission("users"))):
    return db.query(User).order_by(User.created_at.desc()).all()

# --- Gestion équipe : CRÉER un utilisateur ---
@app.post("/admin/users", status_code=201)
@limiter.limit("10 per minute")  # ← Écriture: plus restrictif
async def create_team_user(request: Request, user_data: UserCreateRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    """Crée un nouvel utilisateur d'équipe (manager/cuisine/livreur)"""
    
    if current_admin["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Seul un admin peut créer des comptes d'équipe")
    
    if user_data.username:
        existing = db.query(User).filter((User.username == user_data.username) | (User.phone == user_data.phone)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username ou téléphone déjà utilisé")
    
    # Hash password
    from app.security import get_password_hash
    hashed_password = get_password_hash(user_data.password) if user_data.password else None
    
    # ✅ CRÉATION : is_affiliate=False pour l'équipe (logique métier)
    new_user = User(
        customer_name=user_data.customer_name,
        username=user_data.username,
        phone=user_data.phone,
        hashed_password=hashed_password,
        role=user_data.role,
        permissions=",".join(user_data.permissions) if user_data.permissions else "",
        is_affiliate=False,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"✅ Utilisateur créé: {new_user.username} ({new_user.role})")
    return {"status": "success", "user_id": new_user.id, "message": f"Compte créé pour {new_user.customer_name}"}

# --- Gestion équipe : MODIFIER un utilisateur ---
@app.put("/admin/users/{user_id}")
@limiter.limit("10 per minute")
async def update_team_user(request: Request, user_id: int, update_data: UserUpdateRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    """Modifie le rôle, les permissions ou le statut d'un utilisateur"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    # Protections
    if user.username == current_admin["username"] and update_data.role == "admin":
        raise HTTPException(status_code=403, detail="Action non autorisée sur son propre compte")
    if update_data.role == "admin" and current_admin["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Seul un admin peut créer un autre admin")
    
    # Appliquer les mises à jour
    if update_data.customer_name is not None: user.customer_name = update_data.customer_name
    if update_data.role is not None: user.role = update_data.role
    if update_data.permissions is not None: user.permissions = ",".join(update_data.permissions) if update_data.permissions else ""
    if update_data.is_active is not None: user.is_active = update_data.is_active
    
    db.commit()
    db.refresh(user)
    logger.info(f"✏️ Utilisateur modifié: {user.username} → rôle={user.role}")
    return {"status": "success", "message": f"Profil de {user.customer_name} mis à jour"}

# --- Gestion équipe : SUPPRIMER un utilisateur ---
@app.delete("/admin/users/{user_id}")
@limiter.limit("10 per minute")
async def delete_team_user(request: Request, user_id: int, db: Session = Depends(get_db), current_user: dict = Depends(check_permission("manage_users"))):
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if user_to_delete.username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    if user_to_delete.role in ["admin", "super_admin"] and current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Accès refusé : compte administrateur protégé")
    
    db.delete(user_to_delete)
    db.commit()
    logger.info(f"🗑️ Utilisateur supprimé : #{user_id} par {current_user['username']}")
    return {"message": "Accès révoqué avec succès"}

# ============================================================
# 7️⃣ ROUTES COMMANDES (avec rate limiting)
# ============================================================

@app.post("/orders/create")
@limiter.limit("30 per minute")  # ← Anti-spam commandes
async def create_order(request: Request, order_data: dict, db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")):
    try:
        # Validations
        required = ["customer_name", "product_name", "phone", "zone", "total_amount", "deposit_amount"]
        for field in required:
            if not order_data.get(field):
                raise HTTPException(status_code=400, detail=f"Champ requis manquant : {field}")
        if not validate_cameroon_phone(order_data.get("phone", "")):
            raise HTTPException(status_code=400, detail="Numéro invalide")
        
        # Idempotence
        if idempotency_key:
            existing = db.query(Order).filter(Order.idempotency_key == idempotency_key).first()
            if existing:
                logger.info(f"🔄 Requête idempotente ignorée: {idempotency_key}")
                return {"status": "success", "order_id": existing.id, "duplicate": True}
        
        # Création
        ref_code = order_data.get("affiliate_code")
        new_order = Order(
            customer_name=order_data["customer_name"], product_name=order_data["product_name"],
            phone=order_data["phone"], zone=order_data["zone"],
            total_amount=float(order_data["total_amount"]), deposit_amount=float(order_data["deposit_amount"]),
            portion_size=order_data.get("portion_size"), delivery_date=order_data.get("delivery_date"),
            delivery_time=order_data.get("delivery_time"), complement=order_data.get("complement"),
            affiliate_code=ref_code, affiliate_payout_phone=order_data.get("affiliate_payout_phone"),
            status="en_attente", idempotency_key=idempotency_key
        )
        db.add(new_order)
        
        # Commission affilié
        if ref_code:
            ambassador = db.query(User).filter(User.affiliate_code == ref_code, User.is_affiliate == True).first()
            if ambassador:
                commission = float(order_data["total_amount"]) * 0.15
                ambassador.pending_commissions = (ambassador.pending_commissions or 0) + commission
                logger.info(f"💰 Commission +{commission} FCFA pour {ref_code}")
        
        db.commit()
        db.refresh(new_order)
        
        # Notification push
        if new_order.phone:
            client = db.query(User).filter(User.phone == new_order.phone).first()
            if client and client.expo_push_token:
                asyncio.create_task(ExpoPushService.send_notification(
                    expo_token=client.expo_push_token, title="KemTchop 🍳",
                    body=f"Votre commande de {new_order.product_name} est confirmée !",
                    data={"orderId": new_order.id, "type": "order_confirmed"}
                ))
        
        logger.info(f"✅ Commande #{new_order.id} créée")
        return {"status": "success", "order_id": new_order.id, "duplicate": False}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur création commande : {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Erreur lors de la création")

@app.get("/orders/", response_model=list[OrderResponse])
@limiter.limit("100 per minute")
def list_orders(request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

@app.get("/orders/my-orders/{phone}")
@limiter.limit("60 per minute")
def get_my_orders(request: Request, phone: str, db: Session = Depends(get_db)):
    clean_phone = normalize_phone(phone)
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return db.query(Order).filter(Order.phone == clean_phone).order_by(Order.created_at.desc()).all()

@app.patch("/admin/orders/{order_id}/status")
@limiter.limit("30 per minute")
async def update_order_status(request: Request, order_id: int, new_status: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    old = order.status
    order.status = new_status
    db.commit()
    logger.info(f"📦 Commande #{order_id} : {old} → {new_status}")
    return {"status": "success", "new_status": order.status}

@app.patch("/admin/orders/{order_id}/pay-commission")
@limiter.limit("20 per minute")
async def pay_commission(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    order.commission_paid = True
    db.commit()
    logger.info(f"💸 Commission payée pour commande #{order_id}")
    return {"status": "success", "message": "Commission marquée comme payée"}

# ============================================================
# 8️⃣ ROUTES PRODUITS/REELS (avec rate limiting)
# ============================================================

@app.get("/reels/", response_model=list[ReelResponse])
@limiter.limit("100 per minute")
def get_reels(request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), category: Optional[str] = Query(None), available_only: bool = Query(False)):
    query = db.query(Reel)
    if category and category != "Tout": query = query.filter(Reel.category == category)
    if available_only: query = query.filter(Reel.is_available == True)
    reels = query.order_by(Reel.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for r in reels:
        img = r.image_url.split('/')[-1] if r.image_url else None
        vid = r.video_url.split('/')[-1] if r.video_url else None
        result.append({
            "id": r.id, "title": r.title, "product_name": r.product_name, "category": getattr(r, 'category', "Tout"),
            "is_available": getattr(r, 'is_available', True), "price": r.price,
            "price_solo": getattr(r, 'price_solo', r.price), "price_duo": getattr(r, 'price_duo', r.price * 1.8),
            "price_family": getattr(r, 'price_family', r.price * 3), "family_size": getattr(r, 'family_size', 3),
            "complements": r.complements,
            "image_url": f"{MEDIA_BASE_URL}/videos/{img}" if img else "",
            "thumbnail": f"{MEDIA_BASE_URL}/videos/{img}" if img else "",
            "video_url": f"{MEDIA_BASE_URL}/videos/{vid}" if vid else None
        })
    return result

@app.post("/admin/upload-content")
@limiter.limit("5 per minute")  # ← Upload: très restrictif (lourd)
async def upload_content(request: Request, background_tasks: BackgroundTasks, title: str = Form(...), product_name: str = Form(...), category: str = Form("Grillades"), is_available: str = Form("true"), price_solo: float = Form(...), price_duo: float = Form(...), price_family: float = Form(...), family_size: int = Form(3), complements: str = Form(None), image: UploadFile = File(...), video: Optional[UploadFile] = File(None), db: Session = Depends(get_db)):
    image_ext = image.filename.split('.')[-1].lower()
    image_filename = f"img_{uuid.uuid4().hex}.{'webp' if image_ext in ['jpg','jpeg','png'] else image_ext}"
    image_dest = os.path.join(videos_path, image_filename)
    with open(image_dest, "wb") as buffer: shutil.copyfileobj(image.file, buffer)
    
    final_video_url = None
    if video and video.filename:
        video_ext = video.filename.split('.')[-1]
        temp_fn = f"raw_{uuid.uuid4().hex}.{video_ext}"
        compressed_fn = f"vid_{uuid.uuid4().hex}.mp4"
        temp_path = os.path.join(videos_path, temp_fn)
        final_path = os.path.join(videos_path, compressed_fn)
        with open(temp_path, "wb") as buffer: shutil.copyfileobj(video.file, buffer)
        background_tasks.add_task(compress_video, temp_path, final_path)
        final_video_url = f"{MEDIA_BASE_URL}/videos/{compressed_fn}"
    
    available_bool = str(is_available).lower() in ["true", "1", "yes", "on"]
    new_reel = Reel(
        title=title, product_name=product_name, category=category, is_available=available_bool,
        price=price_solo, price_solo=price_solo, price_duo=price_duo, price_family=price_family,
        family_size=family_size, complements=complements,
        image_url=f"{MEDIA_BASE_URL}/videos/{image_filename}", video_url=final_video_url
    )
    db.add(new_reel)
    db.commit()
    db.refresh(new_reel)
    logger.info(f"🍲 Nouveau plat : {product_name}")
    return {"status": "success", "message": f"Menu {product_name} configuré", "id": new_reel.id}

@app.get("/admin/products")
@limiter.limit("100 per minute")
async def get_admin_products(request: Request, db: Session = Depends(get_db)):
    return db.query(Reel).order_by(Reel.created_at.desc()).all()

@app.delete("/admin/products/{product_id}")
@limiter.limit("10 per minute")
async def delete_product(request: Request, product_id: int, db: Session = Depends(get_db)):
    p = db.query(Reel).filter(Reel.id == product_id).first()
    if not p: raise HTTPException(status_code=404, detail="Plat non trouvé")
    db.delete(p)
    db.commit()
    logger.info(f"🗑️ Plat supprimé : #{product_id}")
    return {"status": "success"}

@app.put("/admin/products/{product_id}/set-hero")
@limiter.limit("10 per minute")
async def set_hero_product(request: Request, product_id: int, db: Session = Depends(get_db)):
    db.query(Reel).update({Reel.is_hero: False})
    p = db.query(Reel).filter(Reel.id == product_id).first()
    if not p: raise HTTPException(status_code=404, detail="Produit non trouvé")
    p.is_hero = True
    db.commit()
    logger.info(f"⭐ Nouveau produit phare : {p.product_name}")
    return {"message": f"{p.product_name} est maintenant le produit phare !"}

# ============================================================
# 9️⃣ ROUTES PARAMÈTRES & ANALYTICS (avec rate limiting)
# ============================================================

@app.get("/admin/settings/delivery-zones")
@limiter.limit("60 per minute")
def get_delivery_settings(request: Request, db: Session = Depends(get_db)):
    settings = db.query(DeliverySettings).first()
    if not settings: return {"zones": ["Bastos", "Akwa", "Bonapriso", "Odza"], "price": 1000}
    return {"zones": settings.zones, "price": settings.base_price}

@app.post("/admin/settings/update-zones")
@limiter.limit("10 per minute")
async def update_delivery_zones(request: Request, data: DeliverySettingsUpdate, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    settings = db.query(DeliverySettings).first()
    if settings:
        settings.zones, settings.base_price = data.zones, data.price
    else:
        settings = DeliverySettings(zones=data.zones, base_price=data.price)
        db.add(settings)
    db.commit()
    logger.info(f"⚙️ Zones livraison mises à jour")
    return {"status": "success", "message": "Paramètres enregistrés"}

@app.get("/admin/stats")
@limiter.limit("60 per minute")
async def get_admin_stats(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(check_permission("dashboard"))):
    try:
        total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
        total_orders = db.query(Order).count()
        total_products = db.query(Reel).filter(Reel.is_available == True).count()
        affiliate_sum = db.query(func.sum(Order.total_amount)).filter(Order.affiliate_code.isnot(None), Order.affiliate_code != "").scalar() or 0
        total_commissions = float(affiliate_sum) * 0.15
        top = db.query(Order.product_name, func.count(Order.product_name).label('count')).filter(Order.status == "termine").group_by(Order.product_name).order_by(func.count(Order.product_name).desc()).first()
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = db.query(Order).filter(Order.created_at >= week_ago).count()
        return {
            "revenue": float(total_revenue), "orders": int(total_orders), "products": int(total_products),
            "top_product": top[0] if top and top[0] else "Aucun",
            "commissions_pending": float(total_commissions), "recent_orders_7d": int(recent)
        }
    except Exception as e:
        logger.error(f"❌ CRASH STATS : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur calcul stats")

@app.get("/admin/payouts/pending")
@limiter.limit("30 per minute")
async def get_pending_payouts(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    orders = db.query(Order).filter(Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.commission_paid == False, Order.status == "termine").all()
    payouts = []
    for o in orders:
        payouts.append({
            "order_id": o.id, "affiliate_code": o.affiliate_code, "amount": round(o.total_amount * 0.15, 2),
            "payout_phone": o.affiliate_payout_phone, "customer": o.customer_name,
            "order_date": o.created_at.isoformat() if o.created_at else None
        })
    return payouts

@app.get("/admin/payouts-summary")
@limiter.limit("30 per minute")
def get_payouts_summary(request: Request, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    summary = db.query(Order.affiliate_code, Order.affiliate_payout_phone, func.sum(Order.total_amount * 0.15).label("total"), func.count(Order.id).label("count")).filter(Order.status == "termine", Order.affiliate_code.isnot(None), Order.affiliate_code != "", Order.commission_paid == False).group_by(Order.affiliate_code, Order.affiliate_payout_phone).all()
    return [{"affiliate_code": r.affiliate_code, "payout_phone": r.affiliate_payout_phone, "total_to_pay": round(float(r.total), 2), "order_count": r.count} for r in summary]

# --- Analytics ---
@app.post("/analytics/track")
@limiter.limit("100 per minute")
async def track_user_event(request: Request, event: AnalyticsEvent, db: Session = Depends(get_db)):
    try:
        db_event = models.UserEvent(
            phone=event.phone, event_type=event.event_type, product_id=event.product_id,
            product_name=event.product_name, video_id=event.video_id, cart_value=event.cart_value,
            affiliate_code=event.affiliate_code, event_metadata=event.event_metadata or {}
        )
        db.add(db_event)
        db.commit()
        logger.info(f"📊 Event tracked: {event.phone} → {event.event_type}")
        return {"status": "success", "message": "Événement enregistré"}
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur tracking : {e}")
        raise HTTPException(status_code=500, detail="Erreur enregistrement")

@app.get("/admin/analytics/abandoned-carts", response_model=List[CampaignTarget])
@limiter.limit("30 per minute")
async def get_abandoned_carts(request: Request, hours: int = Query(48, ge=1, le=168), min_cart_value: float = Query(1000, ge=0), db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    abandonments = db.query(models.UserEvent).filter(and_(models.UserEvent.event_type == 'checkout_abandon', models.UserEvent.created_at >= cutoff, models.UserEvent.cart_value.isnot(None), models.UserEvent.cart_value >= min_cart_value)).order_by(models.UserEvent.created_at.desc()).all()
    
    targets, seen = [], set()
    for ev in abandonments:
        if ev.phone in seen: continue
        has_completed = db.query(models.UserEvent).filter(and_(models.UserEvent.phone == ev.phone, models.UserEvent.event_type == 'order_completed', models.UserEvent.created_at > ev.created_at)).first()
        if not has_completed:
            product = ev.event_metadata.get('last_product') if isinstance(ev.event_metadata, dict) else ev.product_name
            user = db.query(User).filter(User.phone == ev.phone).first()
            targets.append(CampaignTarget(phone=ev.phone, customer_name=user.customer_name if user else "Inconnu", last_event='checkout_abandon', last_event_date=ev.created_at, product_interest=product, cart_value=float(ev.cart_value) if ev.cart_value else 0, total_events=1))
            seen.add(ev.phone)
        if len(targets) >= 100: break
    return targets

@app.get("/admin/analytics/video-interest", response_model=List[CampaignTarget])
@limiter.limit("30 per minute")
async def get_video_interested_users(request: Request, video_id: Optional[int] = Query(None), hours: int = Query(72, ge=1, le=168), db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_affiliates"))):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    viewed = db.query(models.UserEvent.phone, func.max(models.UserEvent.created_at).label('last')).filter(models.UserEvent.event_type == 'video_view', models.UserEvent.created_at >= cutoff)
    if video_id: viewed = viewed.filter(models.UserEvent.video_id == video_id)
    viewed = viewed.group_by(models.UserEvent.phone).all()
    
    targets = []
    for row in viewed:
        converted = db.query(models.UserEvent).filter(models.UserEvent.phone == row.phone, models.UserEvent.event_type == 'order_completed', models.UserEvent.created_at > row.last).first()
        if not converted:
            user = db.query(User).filter(User.phone == row.phone).first()
            targets.append(CampaignTarget(phone=row.phone, customer_name=user.customer_name if user else "Inconnu", last_event='video_view', last_event_date=row.last, product_interest="Vidéo KemTchop", cart_value=None, total_events=1))
        if len(targets) >= 100: break
    return targets

@app.post("/admin/notifications/send")
@limiter.limit("5 per minute")  # ← CRITIQUE: Anti-spam push notifications
async def send_push_campaign(request: Request, campaign: PushCampaignRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    query = db.query(User.expo_push_token).filter(User.expo_push_token.isnot(None), User.expo_push_token != "")
    if campaign.target == "affiliates": query = query.filter(User.is_affiliate == True)
    elif campaign.target.startswith("segment:VIP"):
        query = query.join(Order).filter(Order.status == "termine").having(func.sum(Order.total_amount) >= 50000)
    
    tokens = [t[0] for t in query.distinct().all() if t[0]]
    if not tokens: return {"status": "warning", "message": "Aucun token valide"}
    
    result = await ExpoPushService.send_bulk_notifications(tokens=tokens, title=campaign.title, body=campaign.body, data=campaign.data)
    logger.info(f"📢 Campagne push: {result['success']} envoyés, {result['failed']} échecs")
    return {"status": "success", "sent": result["success"], "failed": result["failed"], "errors": result["errors"][:10]}

# ============================================================
# 🔟 ROUTES PAIEMENT & AFFILIÉS (avec rate limiting)
# ============================================================

@app.post("/payments/campay/init", response_model=PaymentInitResponse)
@limiter.limit("20 per minute")  # ← Paiements: modéré
async def init_campay_payment(request: Request, payment_request: PaymentInitRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == payment_request.order_id, Order.status == "en_attente").first()
    if not order: raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    deposit = round(payment_request.amount * 0.40)
    balance = round(payment_request.amount * 0.60)
    ref = f"KEMTCHOP-{payment_request.order_id}-{deposit}"
    
    try:
        result = await campay_service.create_payment(amount=deposit, description=payment_request.description or f"Acompte #{payment_request.order_id}", reference=ref, phone=payment_request.phone, metadata={"order_id": payment_request.order_id, "total": payment_request.amount, "balance": balance})
        if not result.get("success"): raise HTTPException(status_code=500, detail="Échec initialisation paiement")
        order.campay_reference, order.deposit_amount = ref, deposit
        db.commit()
        logger.info(f"💳 Paiement Campay : {ref} → {deposit} FCFA")
        return PaymentInitResponse(success=True, payment_url=result["payment_url"], reference=ref, deposit_amount=deposit, balance_amount=balance, message=f"Veuillez payer {deposit} FCFA")
    except HTTPException: raise
    except Exception as e:
        logger.error(f"❌ Erreur init Campay : {e}")
        raise HTTPException(status_code=500, detail="Erreur initialisation paiement")

# ============================================================
# ✅ ROUTE ADMIN : Lister toutes les commandes (avec permissions + rate limiting)
# ============================================================

@app.get("/admin/orders", response_model=list[OrderResponse])
@limiter.limit("60 per minute")
async def get_admin_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(check_permission("orders")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """Liste les commandes pour l'admin panel (avec pagination)"""
    
    orders = db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    # Formatage pour le frontend
    return [
        {
            "id": o.id,
            "product_name": o.product_name,
            "customer_name": o.customer_name,
            "phone": o.phone,
            "zone": o.zone,
            "total_amount": float(o.total_amount or 0),
            "deposit_amount": float(o.deposit_amount or 0),
            "status": o.status,
            "portion_size": o.portion_size,
            "delivery_date": o.delivery_date,
            "delivery_time": o.delivery_time,
            "complement": o.complement,
            "created_at": str(o.created_at) if o.created_at else None,
            "affiliate_code": o.affiliate_code,
        }
        for o in orders
    ]

@app.post("/payments/campay/webhook")
@limiter.limit("100 per minute")  # ← Webhooks: permissif (appelés par Campay)
async def campay_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.body()
        signature = request.headers.get("X-Campay-Signature", "")
        if not campay_service.verify_webhook_signature(body, signature):
            logger.warning("⚠️ Signature webhook invalide")
        data = campay_service.parse_webhook_payload(await request.json())
        logger.info(f"🔔 Webhook Campay: {data['reference']} → {data['status']}")
        
        if data["status"] == "SUCCESS" and data["external_reference"]:
            order = db.query(Order).filter(Order.id == data["external_reference"]).first()
            if order:
                order.status = "acompte_paye"
                order.payment_reference = data["reference"]
                db.commit()
                logger.info(f"✅ Commande #{order.id} marquée payée")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"❌ Erreur webhook : {e}")
        return {"status": "error"}

@app.get("/payments/campay/status/{reference}")
@limiter.limit("60 per minute")
async def get_campay_status(request: Request, reference: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.campay_reference == reference).first()
    if order:
        return {"order_id": order.id, "order_status": order.status, "payment_status": getattr(order, 'payment_status', None), "campay_reference": reference}
    return {"status": "not_found"}

# --- Ventes affilié ---
@app.get("/orders/ambassador/{affiliate_code}")
@limiter.limit("60 per minute")
async def get_ambassador_sales(request: Request, affiliate_code: str, db: Session = Depends(get_db)):
    ambassador = db.query(User).filter(User.affiliate_code == affiliate_code, User.is_affiliate == True).first()
    if not ambassador: raise HTTPException(status_code=404, detail="Affilié non trouvé")
    
    orders = db.query(Order).filter(Order.affiliate_code == affiliate_code, Order.status == "termine").order_by(Order.created_at.desc()).all()
    total = sum(float(o.total_amount or 0) for o in orders)
    
    return {
        "affiliate_code": affiliate_code, "ambassador_name": ambassador.customer_name,
        "total_sales": total, "pending_commission": round(total * 0.15, 2), "orders_count": len(orders),
        "orders": [{"id": o.id, "product_name": o.product_name, "customer_name": o.customer_name, "total_amount": float(o.total_amount), "commission": round(float(o.total_amount) * 0.15, 2), "created_at": o.created_at.isoformat() if o.created_at else None, "status": o.status} for o in orders]
    }

# ============================================================
# 🏁 HEALTH CHECK & INITIALISATION
# ============================================================

@app.get("/health")
@limiter.limit("100 per minute")  # ← Health check: permissif
def health_check(request: Request):
    return {"status": "ok", "service": "KemTchop API", "timestamp": datetime.utcnow().isoformat()}

# ✅ Ne pas créer les tables automatiquement en prod (utiliser Alembic)
# Base.metadata.create_all(bind=engine)

logger.info("🚀 KemTchop API démarrée avec succès")

# ============================================================
# 🐍 LAMBDA HANDLER (pour déploiement serverless)
# ============================================================
from mangum import Mangum

# ⚠️ lifespan="auto" est requis pour FastAPI + Mangum
handler = Mangum(app, lifespan="auto")