from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

# Importations de ton projet
from app.database import get_db 
import app.models as models

# Configuration de la sécurité
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
SECRET_KEY = "TON_CODE_SECRET_TRES_LONG_ICI_POUR_KEMTCHOP" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
    
    # Recherche SQL (Username ou Phone)
    user = db.query(models.User).filter(
        (models.User.username == request.username) | (models.User.phone == request.username)
    ).first()
    
    # Vérification identifiants
    if not user or not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides"
        )
    
    # Gestion des permissions (on transforme la chaîne "p1,p2" en liste)
    user_perms = user.permissions.split(",") if user.permissions else []
    
    # Création du token avec Role et Permissions
    token_data = {
        "sub": user.username, 
        "role": user.role, 
        "permissions": user_perms
    }
    token = create_access_token(data=token_data)
    
    return {
        "username": user.customer_name,
        "role": user.role,
        "permissions": user_perms,
        "access_token": token,
        "token_type": "bearer"
    }

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée ou invalide.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        permissions: list = payload.get("permissions", []) # On récupère les perms du token
        
        if username is None:
            raise credentials_exception
            
        return {"username": username, "role": role, "permissions": permissions}
        
    except JWTError:
        raise credentials_exception

# --- NOUVEAU : VERIFICATEUR DE PERMISSIONS FLEXIBLE ---
def check_permissions(required_permission: str):
    """
    Utilisation : Depends(check_permissions("nom_de_la_permission"))
    """
    async def permission_checker(current_user: dict = Depends(get_current_user)):
        # L'admin a toujours tous les droits par défaut
        if current_user.get("role") == "admin":
            return current_user
            
        # Vérification si la permission est dans la liste de l'utilisateur
        if required_permission not in current_user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Accès refusé : Vous n'avez pas la permission [{required_permission}]"
            )
        return current_user
    return permission_checker

# Gardé pour la compatibilité avec tes anciennes routes admin
async def get_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Accès interdit : Seul l'administrateur peut faire cette action."
        )
    return current_user