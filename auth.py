# auth.py - VERSION CORRIGÉE ET COMPLÈTE
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import os
import logging

# Importations de ton projet
from app.database import get_db 
import app.models as models

logger = logging.getLogger("kemtchop.auth")
# Optionnel : configurer le niveau si pas déjà fait ailleurs
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

# ✅ Importer pwd_context depuis app.security (ou définir localement)
try:
    from app.security import pwd_context, verify_password, get_password_hash
except ImportError:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto", pbkdf2_sha256__default_rounds=29000)
    def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
    def get_password_hash(pwd): return pwd_context.hash(pwd)

# Configuration de la sécurité
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    print(f"Tentative de connexion : {request.username}")
    
    user = db.query(models.User).filter(
        (models.User.username == request.username) | (models.User.phone == request.username)
    ).first()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    
    # Parser les permissions (gère chaîne CSV ou tableau)
    user_perms = user.permissions
    if isinstance(user_perms, str):
        user_perms = [p.strip() for p in user_perms.split(",") if p.strip()]
    
    token_data = {
        "sub": user.username, 
        "role": user.role, 
        "permissions": user_perms  # ← Toujours un tableau dans le token
    }
    token = create_access_token(data=token_data)
    
    return {
        "username": user.customer_name,
        "role": user.role,
        "permissions": user_perms,
        "access_token": token,
        "token_type": "bearer"
    }

# auth.py - Dans get_current_user, ajoute ces logs :

async def get_current_user(token: str = Depends(oauth2_scheme)):
    logger.info(f"🔐 Token reçu (début): {token[:30] if token else 'NULL'}...")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée ou invalide.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.info(f"🔑 Décodage avec SECRET_KEY={SECRET_KEY[:10] if SECRET_KEY else 'NULL'}...")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"✅ Token décodé: {payload}")
        
        username: str = payload.get("sub")
        role: str = payload.get("role")
        permissions: list = payload.get("permissions", [])
        
        if username is None:
            logger.warning("⚠️ Username manquant dans payload")
            raise credentials_exception
            
        logger.info(f"👤 Utilisateur authentifié: {username} ({role})")
        return {"username": username, "role": role, "permissions": permissions}
        
    except jwt.ExpiredSignatureError:
        logger.error("⏰ Token expiré")
        raise credentials_exception
    except jwt.InvalidTokenError as e:
        logger.error(f"❌ Token invalide: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {type(e).__name__}: {e}")
        raise credentials_exception

# ✅ NOUVELLE FONCTION : Vérificateur de permissions dynamique
def check_permission(required_permission: str):
    """
    Factory function qui retourne une dépendance pour vérifier une permission.
    Usage: current_user: dict = Depends(check_permission("dashboard"))
    """
    async def permission_checker(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        # ✅ L'admin a TOUS les droits
        if current_user.get("role") == "admin":
            return current_user
        
        # ✅ Pour les autres, vérifier les permissions
        username = current_user.get("username")
        if not username:
            raise HTTPException(status_code=403, detail="Utilisateur non authentifié")
        
        # Option A : Vérifier depuis le token (plus rapide)
        token_perms = current_user.get("permissions", [])
        if isinstance(token_perms, str):
            token_perms = [p.strip() for p in token_perms.split(",") if p.strip()]
        
        if required_permission in token_perms:
            return current_user
        
        # Option B : Fallback - vérifier en base de données (plus fiable)
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=403, detail="Utilisateur non trouvé")
        
        db_perms = user.permissions
        if isinstance(db_perms, str):
            db_perms = [p.strip() for p in db_perms.split(",") if p.strip()]
        
        if required_permission not in (db_perms or []):
            raise HTTPException(
                status_code=403, 
                detail=f"Accès refusé : Permission '{required_permission}' requise"
            )
        
        return current_user
    
    return permission_checker

# Gardé pour compatibilité : vérifie que l'utilisateur est admin
async def get_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Accès interdit : Seul l'administrateur peut faire cette action."
        )
    return current_user

# Gardé pour compatibilité avec l'ancien nom
def check_permissions(required_permission: str):
    """Alias pour check_permission (ancien nom)"""
    return check_permission(required_permission)