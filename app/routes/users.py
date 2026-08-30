# app/routes/users.py
# ============================================================
# 👤 ROUTES UTILISATEURS - KemTchop API
# ============================================================

import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import os 
import uuid 
from fastapi import APIRouter, Request, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt

from app.database import get_db
from app.entities import User, Order, PasswordResetToken
from app.auth import get_current_user, check_permission
from app.config import settings
from app.security import pwd_context, verify_password, get_password_hash

# ============================================================
# 🔧 CONFIG
# ============================================================
router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger("kemtchop")
limiter = Limiter(key_func=get_remote_address)

def validate_cameroon_phone(phone: str) -> bool:
    clean = re.sub(r'\D', '', phone)
    return bool(re.match(r'^(237)?6[0-9]{8}$', clean))

def normalize_phone(phone: str) -> str:
    return re.sub(r'\D', '', phone)

def generate_unique_code(phone: str) -> str:
    import random, string
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    return f"KEM-{phone[-4:]}-{letters}"

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# ============================================================
# 📋 PYDANTIC SCHEMAS
# ============================================================
from pydantic import BaseModel, Field, field_validator

class RegisterRequest(BaseModel):
    name: str
    phone: str
    password: str
    class Config:
        from_attributes = True
        extra = "ignore"

class UserAuth(BaseModel):
    phone: str
    password: str

class TokenUpdateRequest(BaseModel):
    phone: str
    expo_token: str

class AddressCreate(BaseModel):
    phone: str
    city: str
    neighborhood: str
    details: str
    label: str

class ActivateAffiliateRequest(BaseModel):
    phone: str

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
    customer_name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = Field(None, pattern="^(admin|manager|cuisine|livreur|customer)$")
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

# ============================================================
# 🔐 AUTHENTIFICATION & INSCRIPTION
# ============================================================
@router.post("/register")
@limiter.limit("10 per minute")
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

@router.post("/login")
@limiter.limit("5 per minute; 20 per hour")
async def login(request: Request, user_data: UserAuth, db: Session = Depends(get_db)):
    clean_phone = normalize_phone(user_data.phone)
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user or not pwd_context.verify(user_data.password, user.hashed_password):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"🚨 Échec login pour '{clean_phone}' depuis {client_ip}")
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    
    logger.info(f"✅ Connexion : {user.phone}")

    # Génération du token JWT
    from app.auth import create_access_token
    user_perms = user.permissions
    if isinstance(user_perms, str):
        user_perms = [p.strip() for p in user_perms.split(",") if p.strip()]

    token_data = {
        "sub": user.username or user.phone,
        "role": user.role or "customer",
        "phone": user.phone,
        "permissions": user_perms
    }
    access_token = create_access_token(data=token_data)

    return {
        "status": "success",
        "user_name": user.customer_name,
        "is_affiliate": user.is_affiliate,
        "affiliate_code": user.affiliate_code,
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/update-token")
@limiter.limit("30 per minute")
async def update_user_token(
    request: Request, 
    data: TokenUpdateRequest, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authenticated_phone = current_user.get("phone")
    if not authenticated_phone:
        logger.warning("🚨 Tentative de mise à jour token sans téléphone dans le JWT")
        raise HTTPException(status_code=403, detail="Identifiant manquant dans la session")
    
    expo_token = data.expo_token.strip() if data.expo_token else ""
    if not expo_token.startswith("ExponentPushToken[") and not expo_token.startswith("ExpoPushToken["):
        logger.warning(f"⚠️ Format de token Expo invalide pour {authenticated_phone}")
    
    user = db.query(User).filter(User.phone == authenticated_phone).first()
    if not user:
        logger.warning(f"🚨 Utilisateur {authenticated_phone} introuvable en BDD")
        raise HTTPException(status_code=404, detail="Compte utilisateur introuvable")
    
    user.expo_push_token = expo_token
    user.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"🔔 Token Expo mis à jour pour {authenticated_phone}")
    return {"status": "success", "message": "Token de notification mis à jour"}

@router.post("/add-address")
@limiter.limit("20 per minute")
async def add_address(request: Request, address: AddressCreate, db: Session = Depends(get_db)):
    if not validate_cameroon_phone(address.phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    if not db.query(User).filter(User.phone == address.phone).first():
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    logger.info(f"📍 Nouvelle adresse pour {address.phone}")
    return {"status": "success", "message": "Adresse enregistrée"}

# ============================================================
# 🔑 GESTION DES MOTS DE PASSE
# ============================================================
@router.post("/generate-reset-link/{phone}")
@limiter.limit("10 per minute")
def generate_reset_link(request: Request, phone: str, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
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

@router.post("/complete-setup")
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

@router.post("/reset-password")
@limiter.limit("10 per minute")
async def reset_password(request: Request, data: dict, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
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

# ============================================================
# 📊 STATUT & AFFILIATION
# ============================================================
@router.get("/status")
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
        from app.enums import OrderStatus
        total_sales = db.query(func.sum(Order.total_amount)).filter(
            Order.affiliate_code == user.affiliate_code,
            Order.status == OrderStatus.DELIVERED.value,
            Order.commission_paid == False
        ).scalar() or 0
        pending = float(total_sales) * 0.15
    
    return {
        "exists": True, "needs_setup": False, "is_affiliate": user.is_affiliate,
        "affiliate_code": user.affiliate_code, "pending_commissions": pending, "user_name": user.customer_name
    }

@router.patch("/request-affiliate")
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
# 👥 ADMIN : GESTION DES UTILISATEURS
# ============================================================
@router.post("/activate-affiliate")
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

@router.get("/all", response_model=List[UserResponse])
@limiter.limit("60 per minute")
def get_all_users(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(check_permission("users"))):
    return db.query(User).order_by(User.created_at.desc()).all()

@router.post("/create-team", status_code=201)
@limiter.limit("10 per minute")
async def create_team_user(request: Request, user_data: UserCreateRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    if current_admin["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Seul un admin peut créer des comptes d'équipe")
    
    if user_data.username:
        existing = db.query(User).filter((User.username == user_data.username) | (User.phone == user_data.phone)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username ou téléphone déjà utilisé")
    
    from app.security import get_password_hash
    hashed_password = get_password_hash(user_data.password) if user_data.password else None
    
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

@router.put("/team/{user_id}")
@limiter.limit("10 per minute")
async def update_team_user(request: Request, user_id: int, update_data: UserUpdateRequest, db: Session = Depends(get_db), current_admin: dict = Depends(check_permission("manage_users"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if user.username == current_admin["username"] and update_data.role == "admin":
        raise HTTPException(status_code=403, detail="Action non autorisée sur son propre compte")
    if update_data.role == "admin" and current_admin["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Seul un admin peut créer un autre admin")
    
    if update_data.customer_name is not None: user.customer_name = update_data.customer_name
    if update_data.role is not None: user.role = update_data.role
    if update_data.permissions is not None: user.permissions = ",".join(update_data.permissions) if update_data.permissions else ""
    if update_data.is_active is not None: user.is_active = update_data.is_active
    
    db.commit()
    db.refresh(user)
    logger.info(f"✏️ Utilisateur modifié: {user.username} → rôle={user.role}")
    return {"status": "success", "message": f"Profil de {user.customer_name} mis à jour"}

@router.delete("/team/{user_id}")
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