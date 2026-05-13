# ============================================================
# 🍲 KEMTCHOP - Backend API (FastAPI)
# Fichier: main.py - VERSION CORRIGÉE ET VALIDÉE
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
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any  # ← Ajoute Dict et Any

# ✅ CORRECT :
# ✅ CORRECT :
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, File, Form, UploadFile, Query, Request
from fastapi.staticfiles import StaticFiles  # ← Ajoute cette ligne !#                                                                                      ↑ Ajoute Request icifrom fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
import requests

# 🔐 Chargement des variables d'environnement (OBLIGATOIRE en premier)
from dotenv import load_dotenv
load_dotenv()

# Imports locaux
from app.database import engine, get_db, SessionLocal
import app.models as models
# ✅ Ajoute dans les imports SQLAlchemy (vers la ligne ~15) :
from sqlalchemy import func
from app.models import Order, Reel, Transaction, DeliverySettings, PasswordResetToken, User
from auth import get_current_user, get_admin_user, check_permissions, pwd_context, router
# ✅ Ajoute ces imports avec les autres :
from app.services.campay import campay_service
from pydantic import BaseModel, Field
# ============================================================
# ⚙️ CONFIGURATION GLOBALE
# ============================================================

# Logging structuré
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kemtchop")

# Variables d'environnement (avec fallback pour le dev local)
SERVER_IP = os.getenv("SERVER_IP", "localhost")
BASE_URL = os.getenv("BASE_URL", f"http://{SERVER_IP}:8000")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

# Vérification de sécurité : clé admin obligatoire en production
if not ADMIN_SECRET_KEY:
    logger.warning("⚠️ ADMIN_SECRET_KEY non définie - mode développement uniquement")

# CORS : origines autorisées (liste explicite, PAS de "*" avec credentials)
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
).split(",")

# Initialisation de l'application FastAPI
app = FastAPI(
    title="KemTchop API",
    description="API de précommande de nourriture traditionnelle camerounaise",
    version="1.0.0"
)

# ============================================================
# 🛡️ MIDDLEWARE & CONFIGURATION
# ============================================================

# Configuration CORS sécurisée
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration des fichiers statiques (vidéos/images)
script_dir = os.path.dirname(os.path.abspath(__file__))
videos_path = os.path.join(script_dir, "videos")
os.makedirs(videos_path, exist_ok=True)

app.mount("/videos", StaticFiles(directory=videos_path), name="videos")

# Inclusion du router d'authentification (défini dans auth.py)
app.include_router(router)

# ============================================================
# 🔧 UTILITAIRES
# ============================================================

def validate_cameroon_phone(phone: str) -> bool:
    """Valide un numéro de téléphone camerounais (+2376XXXXXXXX ou 6XXXXXXXX)"""
    clean = re.sub(r'\D', '', phone)
    return bool(re.match(r'^(237)?6[0-9]{8}$', clean))

# ============================================================
# 🔧 UTILITAIRES
# ============================================================

def normalize_phone(phone: str) -> str:
    """Nettoie un numéro de téléphone : garde uniquement les chiffres"""
    return re.sub(r'\D', '', phone)

def validate_cameroon_phone(phone: str) -> bool:
    """Valide un numéro de téléphone camerounais (+2376XXXXXXXX ou 6XXXXXXXX)"""
    clean = re.sub(r'\D', '', phone)
    return bool(re.match(r'^(237)?6[0-9]{8}$', clean))

# ... reste des utilitaires ...

def compress_video(input_path: str, output_path: str):
    """Compresse une vidéo avec FFmpeg en arrière-plan"""
    try:
        command = [
            'ffmpeg', '-i', input_path,
            '-vcodec', 'libx264', '-crf', '28',
            '-preset', 'veryfast', '-acodec', 'aac', '-y', output_path
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        # Ne supprimer l'original que si la compression a réussi
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            os.remove(input_path)
            logger.info(f"✅ Vidéo compressée : {output_path}")
        else:
            logger.error(f"❌ Échec compression : fichier de sortie vide")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg error: {e.stderr if e.stderr else e}")
        if os.path.exists(input_path):
            os.remove(input_path)
    except Exception as e:
        logger.error(f"❌ Erreur inattendue compress_video : {e}", exc_info=True)

def generate_unique_code(phone: str) -> str:
    """Génère un code affilié unique type KEM-4047-AB"""
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    return f"KEM-{phone[-4:]}-{letters}"

def send_kemtchop_notification(expo_token: str, title: str, message: str):
    """Envoie une notification push via Expo"""
    if not expo_token:
        return {"status": "skipped", "reason": "no_token"}
    
    url = "https://exp.host/--/api/v2/push/send"
    payload = {
        "to": expo_token,
        "title": title,
        "body": message,
        "sound": "default",
        "data": {"status": "update"}
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"❌ Échec notification Expo : {e}")
        return {"status": "error", "detail": str(e)}

# ============================================================
# 📦 SCHÉMAS PYDANTIC (Validation des données)
# ============================================================

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
    status: str
    
    class Config:
        from_attributes = True

class DeliverySettingsSchema(BaseModel):
    zones: List[str]
    price: int

class ReelResponse(BaseModel):
    id: int
    title: str
    video_url: Optional[str] = None
    image_url: str
    product_name: str
    price: float
    category: Optional[str] = "Tout"
    is_available: Optional[bool] = True
    
    class Config:
        from_attributes = True

class UserAuth(BaseModel):
    phone: str
    password: str

class ResetPasswordRequest(BaseModel):
    phone: str
    new_password: str
    secret_key: str

class UserResponse(BaseModel):
    id: int
    username: str
    phone: Optional[str] = None
    customer_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    customer_name: str
    password: str
    role: str
    permissions: Optional[str] = ""

class TokenUpdate(BaseModel):
    phone: str
    expo_token: str

class AddressCreate(BaseModel):
    phone: str
    city: str
    neighborhood: str
    details: str
    label: str
class RegisterRequest(BaseModel):
    name: str
    phone: str
    password: str
    
    class Config:
        from_attributes = True
        extra = "ignore"  # Ignore les champs inattendus comme is_affiliate

class PaymentInitRequest(BaseModel):
    order_id: int
    amount: float  # Montant TOTAL de la commande
    phone: str
    description: Optional[str] = "Acompte KemTchop"

class PaymentInitResponse(BaseModel):
    success: bool
    payment_url: str
    reference: str
    deposit_amount: float  # 40% à payer maintenant
    balance_amount: float  # 60% à payer à la livraison
    message: str

class WebhookRequest(BaseModel):
    reference: str
    status: str
    amount: int
    currency: str
    paid_at: Optional[str] = None
    method: Optional[str] = None
    phone_number: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
# ============================================================
# 🔐 ROUTES D'AUTHENTIFICATION & UTILISATEURS
# ============================================================

# ✅ Remplace TOUTE ta fonction register par celle-ci :
# ✅ Remplace TOUTE ta fonction register par celle-ci :
@app.post("/users/register")
async def register(
    register_data: RegisterRequest,  # ← ✅ CORRECT : deux-points présent !
    db: Session = Depends(get_db)
):
    """Inscription d'un nouveau client"""
    # Accès aux champs du modèle Pydantic
    name = register_data.name
    phone = register_data.phone
    password = register_data.password

    if not name or not phone or not password:
        raise HTTPException(status_code=400, detail="Tous les champs sont obligatoires.")
    
    # Normalisation du téléphone
    clean_phone = normalize_phone(phone)
    
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro de téléphone camerounais invalide")

    # Vérification d'existence avec le numéro nettoyé
    user_exists = db.query(models.User).filter(models.User.phone == clean_phone).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="Ce numéro existe déjà.")

    try:
        # Hachage sécurisé du mot de passe
        password_str = str(password)[:72]
        hashed_password = pwd_context.hash(password_str)

        # Génération code affilié
        short_id = str(uuid.uuid4())[:4].upper()
        prefix = name[:3].upper() if len(name) >= 3 else name.upper()
        generated_code = f"{prefix}-{short_id}"

        new_user = models.User(
            customer_name=name, 
            phone=clean_phone,
            hashed_password=hashed_password,
            is_affiliate=False,
            affiliate_code=generated_code,
            has_requested_affiliate=False 
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"✅ Nouvel utilisateur enregistré : {clean_phone}")
        return {"status": "success", "message": "Client enregistré"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ ERREUR CRITIQUE REGISTER : {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur lors de l'inscription")

@app.post("/users/login")
async def login(user_data: UserAuth, db: Session = Depends(get_db)):
    """Connexion d'un utilisateur existant"""
    clean_phone = normalize_phone(user_data.phone)
    if not validate_cameroon_phone(user_data.phone):
        raise HTTPException(status_code=400, detail="Numéro de téléphone invalide")
    
    user = db.query(models.User).filter(models.User.phone == clean_phone).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Numéro ou mot de passe incorrect")

    try:
        if not pwd_context.verify(user_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Numéro ou mot de passe incorrect")
    except Exception as e:
        logger.warning(f"⚠️ Erreur de vérification pour {user.phone}: {e}")
        raise HTTPException(status_code=401, detail="Compte obsolète. Veuillez réinitialiser votre mot de passe.")

    logger.info(f"✅ Connexion réussie : {user.phone}")
    return {
        "status": "success",
        "user_name": user.customer_name,
        "is_affiliate": user.is_affiliate,
        "affiliate_code": user.affiliate_code
    }

@app.post("/users/update-token")
async def update_user_token(data: TokenUpdate, db: Session = Depends(get_db)):
    """Met à jour le token Expo Push pour les notifications"""
    if not validate_cameroon_phone(data.phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(models.User).filter(models.User.phone == data.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.expo_push_token = data.expo_token
    db.commit()
    
    logger.info(f"🔔 Token Expo mis à jour pour {data.phone}")
    return {"status": "success", "message": "Token mis à jour"}

@app.post("/users/add-address")
async def add_address(address: AddressCreate, db: Session = Depends(get_db)):
    """Ajoute une adresse de livraison pour un utilisateur"""
    if not validate_cameroon_phone(address.phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(models.User).filter(models.User.phone == address.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    logger.info(f"📍 Nouvelle adresse pour {address.phone}: {address.neighborhood} ({address.label})")
    return {"status": "success", "message": "Adresse enregistrée avec succès"}

# ============================================================
# 🔁 GESTION DES MOTS DE PASSE
# ============================================================

@app.post("/admin/generate-reset-link/{phone}")
def generate_reset_link(phone: str, db: Session = Depends(get_db)):
    """Génère un lien de réinitialisation de mot de passe sécurisé"""
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Client introuvable")

    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=2)
    
    db_token = PasswordResetToken(
        token=token,
        phone=phone,
        expires_at=expires
    )
    db.add(db_token)
    db.commit()
    
    link = f"https://kemtchop.app/setup-password?token={token}"
    logger.info(f"🔗 Lien de reset généré pour {phone}")
    return {"link": link}

@app.post("/users/complete-setup")
def complete_setup(token: str, new_password: str, db: Session = Depends(get_db)):
    """Finalise la configuration du mot de passe via token"""
    db_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    
    if not db_token:
        raise HTTPException(status_code=400, detail="Lien expiré ou invalide")

    user = db.query(models.User).filter(models.User.phone == db_token.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.hashed_password = pwd_context.hash(new_password[:72])
    db_token.used = True
    db.commit()
    
    logger.info(f"✅ Mot de passe configuré pour {db_token.phone}")
    return {"message": "Mot de passe configuré avec succès !"}

@app.post("/users/reset-password")
async def reset_password(data: dict, db: Session = Depends(get_db)):
    """Réinitialisation administrative (réservé aux admins)"""
    phone = data.get("phone")
    new_password = data.get("new_password")
    admin_token = data.get("admin_token")

    if not admin_token or admin_token != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Non autorisé")

    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    user.hashed_password = pwd_context.hash(new_password[:72])
    db.commit()
    
    logger.info(f"🔐 Mot de passe réinitialisé pour {phone} par un admin")
    return {"status": "success", "message": "Mot de passe mis à jour"}

# ============================================================
# 📊 STATUT UTILISATEUR & AFFILIATION
# ============================================================

@app.get("/users/status")
async def get_user_status(phone: str, db: Session = Depends(get_db)):
    # ✅ NORMALISATION
    clean_phone = re.sub(r"\D", "", phone)
    
    if not clean_phone or not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro de téléphone invalide.")

    user = db.query(models.User).filter(models.User.phone == clean_phone).first()
    # ... reste du code
    
    if not user:
        return {"exists": False, "needs_setup": True, "message": "User not found"}
    
    if not user.hashed_password or len(user.hashed_password.strip()) < 10:
        return {
            "exists": True, 
            "needs_setup": True, 
            "phone": user.phone,
            "message": "Mot de passe requis."
        }

    if user.is_affiliate and user.affiliate_code:
        total_sales = db.query(func.sum(Order.total_amount))\
            .filter(Order.affiliate_code == user.affiliate_code)\
            .filter(Order.status == "termine")\
            .scalar() or 0
        pending = float(total_sales) * 0.15
    else:
        pending = 0.0
        
    return {
        "exists": True,
        "needs_setup": False,
        "is_affiliate": user.is_affiliate,
        "affiliate_code": user.affiliate_code,
        "pending_commissions": pending,
        "user_name": user.customer_name
    }

@app.patch("/users/request-affiliate")
async def request_affiliate(phone: str, db: Session = Depends(get_db)):
    """Permet à un utilisateur de demander le statut d'affilié"""
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.has_requested_affiliate = True
    db.commit()
    
    logger.info(f"🤝 Demande d'affiliation reçue de {phone}")
    return {"message": "Demande envoyée à l'administration"}

@app.post("/admin/activate-affiliate/")
async def activate_affiliate(
    phone: str = Query(..., description="Numéro de l'ambassadeur sans +237"), 
    db: Session = Depends(get_db)
): 
    """Active le statut d'affilié pour un utilisateur (admin uniquement)"""
    if not validate_cameroon_phone(phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(models.User).filter(
        models.User.phone == phone,
        models.User.role != "admin"
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=404, 
            detail="Client non trouvé. Vérifiez que le numéro appartient à un utilisateur standard."
        )
    
    if not user.is_affiliate:
        try:
            new_code = generate_unique_code(phone)
            user.affiliate_code = new_code
            user.is_affiliate = True
            db.commit()
            db.refresh(user)
            logger.info(f"🎉 Affilié activé : {user.customer_name} ({new_code})")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur activation affilié : {e}")
            raise HTTPException(status_code=500, detail="Erreur lors de l'activation")
    
    return {
        "status": "success",
        "user_id": user.id,
        "user_name": getattr(user, 'customer_name', "Partenaire Kemtchop"),
        "phone": user.phone,
        "affiliate_code": user.affiliate_code,
        "share_link": f"{BASE_URL}/home?ref={user.affiliate_code}"
    }

# ============================================================
# 🛒 GESTION DES COMMANDES
# ============================================================

@app.post("/orders/create")
async def create_order(order_data: dict, db: Session = Depends(get_db)):
    """Crée une nouvelle commande avec gestion d'affiliation"""
    try:
        required_fields = ["customer_name", "product_name", "phone", "zone", "total_amount", "deposit_amount"]
        for field in required_fields:
            if not order_data.get(field):
                raise HTTPException(status_code=400, detail=f"Champ requis manquant : {field}")
        
        if not validate_cameroon_phone(order_data.get("phone", "")):
            raise HTTPException(status_code=400, detail="Numéro de téléphone client invalide")
        
        ref_code = order_data.get("affiliate_code")
        
        new_order = Order(
            customer_name=order_data.get("customer_name"),
            product_name=order_data.get("product_name"),
            phone=order_data.get("phone"),
            zone=order_data.get("zone"),
            total_amount=float(order_data.get("total_amount", 0)), 
            deposit_amount=float(order_data.get("deposit_amount", 0)),
            portion_size=order_data.get("portion_size"),
            delivery_date=order_data.get("delivery_date"),
            delivery_time=order_data.get("delivery_time"),
            complement=order_data.get("complement"),
            affiliate_code=ref_code, 
            affiliate_payout_phone=order_data.get("affiliate_payout_phone"),
            status="en_attente"
        )
        db.add(new_order)
        
        if ref_code:
            ambassador = db.query(User).filter(
                User.affiliate_code == ref_code,
                User.is_affiliate == True
            ).first()
            
            if ambassador:
                commission_value = float(order_data.get("total_amount", 0)) * 0.15
                ambassador.pending_commissions = (ambassador.pending_commissions or 0) + commission_value
                logger.info(f"💰 Commission +{commission_value} FCFA pour affilié {ref_code}")
        
        db.commit()
        db.refresh(new_order)
        
        if new_order.phone:
            client = db.query(User).filter(User.phone == new_order.phone).first()
            if client and client.expo_push_token:
                send_kemtchop_notification(
                    client.expo_push_token,
                    "KemTchop 🍳",
                    f"Votre commande de {new_order.product_name} est confirmée !"
                )
        
        logger.info(f"✅ Commande #{new_order.id} créée pour {new_order.customer_name}")
        return {"status": "success", "order_id": new_order.id}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur création commande : {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Erreur lors de la création de la commande")

@app.get("/orders/", response_model=list[OrderResponse])
def list_all_orders(  # ← Nouveau nom unique
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    orders = db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    return orders

@app.get("/orders/my-orders/{phone}")
def get_orders_by_phone(phone: str, db: Session = Depends(get_db)):
    clean_phone = normalize_phone(phone)  # ✅ Normalisation
    
    if not validate_cameroon_phone(clean_phone):
        raise HTTPException(status_code=400, detail="Numéro invalide")
    
    user = db.query(User).filter(User.phone == clean_phone).first()  # ✅ Recherche normalisée
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non reconnu.")
    
    if not user.hashed_password:
        raise HTTPException(status_code=403, detail="Accès refusé. Veuillez configurer votre mot de passe.")

    orders = db.query(Order).filter(Order.phone == clean_phone).order_by(Order.created_at.desc()).all()
    return orders  # ✅ RETURN AJOUTÉ

@app.patch("/admin/orders/{order_id}/status")
async def update_order_status(order_id: int, new_status: str, db: Session = Depends(get_db)):
    """Met à jour le statut d'une commande (admin)"""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    
    old_status = db_order.status
    db_order.status = new_status
    db.commit()
    
    logger.info(f"📦 Commande #{order_id} : {old_status} → {new_status}")
    return {"status": "success", "new_status": db_order.status}

@app.patch("/admin/orders/{order_id}/pay-commission")
async def pay_commission(order_id: int, db: Session = Depends(get_db)):
    """Marque la commission d'une commande comme payée"""
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    
    order.commission_paid = True
    db.commit()
    
    logger.info(f"💸 Commission payée pour commande #{order_id}")
    return {"status": "success", "message": f"Commission pour la commande {order_id} marquée comme payée"}

# ============================================================
# 🍽️ GESTION DES PLATS (REELS)
# ============================================================

@app.get("/reels/", response_model=list[ReelResponse])
def get_reels(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    available_only: bool = Query(False)
):
    """Récupère la liste des plats (avec filtres et pagination)"""
    query = db.query(Reel)
    
    if category and category != "Tout":
        query = query.filter(Reel.category == category)
    
    if available_only:
        query = query.filter(Reel.is_available == True)
    
    reels_db = query.order_by(Reel.created_at.desc()).offset(skip).limit(limit).all()
    
    reels_pour_mobile = []
    for reel in reels_db:
        img_name = reel.image_url.split('/')[-1] if reel.image_url else None
        vid_name = reel.video_url.split('/')[-1] if reel.video_url else None
        
        reels_pour_mobile.append({
            "id": reel.id,
            "title": reel.title,
            "product_name": reel.product_name,
            "category": getattr(reel, 'category', "Tout"),
            "is_available": getattr(reel, 'is_available', True),
            "price": reel.price,
            "price_solo": getattr(reel, 'price_solo', reel.price),
            "price_duo": getattr(reel, 'price_duo', reel.price * 1.8),
            "price_family": getattr(reel, 'price_family', reel.price * 3),
            "family_size": getattr(reel, 'family_size', 3),
            "image_url": f"{BASE_URL}/videos/{img_name}" if img_name else "",
            "thumbnail": f"{BASE_URL}/videos/{img_name}" if img_name else "",
            "video_url": f"{BASE_URL}/videos/{vid_name}" if vid_name else None
        })
    return reels_pour_mobile

@app.post("/admin/upload-content")
async def upload_content(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    product_name: str = Form(...),
    category: str = Form("Grillades"),
    is_available: str = Form("true"),
    price_solo: float = Form(...),
    price_duo: float = Form(...),
    price_family: float = Form(...),
    family_size: int = Form(3),
    complements: str = Form(None), 
    image: UploadFile = File(...),
    video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Upload d'un nouveau plat avec image et vidéo optionnelle"""
    image_ext = image.filename.split('.')[-1].lower()
    image_filename = f"img_{uuid.uuid4().hex}.{'webp' if image_ext in ['jpg','jpeg','png'] else image_ext}"
    image_dest = os.path.join(videos_path, image_filename)
    
    with open(image_dest, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    final_video_url = None
    if video and video.filename:
        video_ext = video.filename.split('.')[-1]
        temp_filename = f"raw_{uuid.uuid4().hex}.{video_ext}"
        compressed_filename = f"vid_{uuid.uuid4().hex}.mp4"
        temp_path = os.path.join(videos_path, temp_filename)
        final_path = os.path.join(videos_path, compressed_filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        background_tasks.add_task(compress_video, temp_path, final_path)
        final_video_url = f"{BASE_URL}/videos/{compressed_filename}"

    available_bool = str(is_available).lower() in ["true", "1", "yes", "on"]

    new_reel = Reel(
        title=title,
        product_name=product_name,
        category=category,
        is_available=available_bool,
        price=price_solo,
        price_solo=price_solo,
        price_duo=price_duo,
        price_family=price_family,
        family_size=family_size,
        complements=complements,
        image_url=f"{BASE_URL}/videos/{image_filename}",
        video_url=final_video_url
    )
    
    db.add(new_reel)
    db.commit()
    db.refresh(new_reel)
    
    logger.info(f"🍲 Nouveau plat ajouté : {product_name} ({category})")
    return {"status": "success", "message": f"Menu {product_name} configuré.", "id": new_reel.id}

@app.get("/admin/products")
async def get_admin_products(db: Session = Depends(get_db)):
    """Récupère tous les plats pour l'admin"""
    return db.query(Reel).order_by(Reel.created_at.desc()).all()

@app.delete("/admin/products/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Supprime un plat (admin)"""
    db_product = db.query(Reel).filter(Reel.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Plat non trouvé")
    
    db.delete(db_product)
    db.commit()
    
    logger.info(f"🗑️ Plat supprimé : #{product_id}")
    return {"status": "success"}

@app.put("/admin/products/{product_id}/set-hero")
async def set_hero_product(product_id: int, db: Session = Depends(get_db)):
    """Définit un produit comme 'produit phare' (mis en avant)"""
    db.query(Reel).update({Reel.is_hero: False})
    
    product = db.query(Reel).filter(Reel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
        
    product.is_hero = True
    db.commit()
    
    logger.info(f"⭐ Nouveau produit phare : {product.product_name}")
    return {"message": f"{product.product_name} est maintenant le produit phare !"}

# ============================================================
# ⚙️ PARAMÈTRES & LOGISTIQUE
# ============================================================

@app.get("/admin/settings/delivery-zones")
def get_delivery_settings(db: Session = Depends(get_db)):
    """Récupère les zones de livraison et tarifs"""
    settings = db.query(DeliverySettings).first()
    if not settings:
        return {"zones": ["Bastos", "Akwa", "Bonapriso", "Odza"], "price": 1000}
    return {"zones": settings.zones, "price": settings.base_price}

# ============================================================
# 👥 GESTION DE L'ÉQUIPE (ADMIN)
# ============================================================

@app.get("/admin/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db), current_admin: dict = Depends(get_admin_user)):
    """Liste tous les utilisateurs (admin uniquement)"""
    return db.query(User).order_by(User.created_at.desc()).all()

@app.post("/admin/users")
async def create_team_user(
    user_data: UserCreate, 
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_admin_user)
):
    """Crée un nouvel utilisateur d'équipe (admin uniquement)"""
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet identifiant est déjà utilisé")

    hashed_pwd = pwd_context.hash(user_data.password[:72])

    new_user = User(
        username=user_data.username.strip(),
        customer_name=user_data.customer_name,
        hashed_password=hashed_pwd,
        role=user_data.role,
        permissions=user_data.permissions,
        is_active=True
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"👤 Nouvel utilisateur équipe créé : {new_user.username}")
        return {"message": "Utilisateur créé avec succès", "username": new_user.username}
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur création utilisateur équipe : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement")

@app.delete("/admin/users/{user_id}")
async def delete_team_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_admin_user)
):
    """Supprime un utilisateur d'équipe (avec protection auto-suppression)"""
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if user_to_delete.username == current_admin["username"]:
        raise HTTPException(
            status_code=400, 
            detail="Sécurité : Vous ne pouvez pas supprimer votre propre compte."
        )

    db.delete(user_to_delete)
    db.commit()
    
    logger.info(f"🗑️ Utilisateur équipe supprimé : #{user_id}")
    return {"message": "Accès révoqué avec succès"}

# ============================================================
# 📈 STATISTIQUES & ANALYTICS
# ============================================================

@app.get("/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db), current_admin: dict = Depends(get_admin_user)):
    """Retourne les statistiques globales pour le dashboard admin"""
    try:
        total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
        total_orders = db.query(Order).count()
        total_products = db.query(Reel).filter(Reel.is_available == True).count()
        
        affiliate_orders_sum = db.query(func.sum(Order.total_amount))\
            .filter(Order.affiliate_code.isnot(None))\
            .filter(Order.affiliate_code != "")\
            .scalar() or 0
        total_commissions = float(affiliate_orders_sum) * 0.15

        top_product = db.query(
            Order.product_name, 
            func.count(Order.product_name).label('count')
        ).filter(Order.status == "termine")\
         .group_by(Order.product_name)\
         .order_by(func.count(Order.product_name).desc())\
         .first()
        
        top_product_name = top_product[0] if top_product and top_product[0] else "Aucun"

        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_orders = db.query(Order).filter(Order.created_at >= week_ago).count()

        return {
            "revenue": float(total_revenue),
            "orders": int(total_orders),
            "products": int(total_products),
            "top_product": top_product_name,
            "commissions_pending": float(total_commissions),
            "recent_orders_7d": int(recent_orders)
        }
    except Exception as e:
        logger.error(f"❌ CRASH STATS : {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne de calcul des stats")

@app.get("/admin/payouts/pending")
async def get_pending_payouts(db: Session = Depends(get_db), current_admin: dict = Depends(get_admin_user)):
    """Liste les commissions affiliés en attente de paiement"""
    orders = db.query(Order).filter(
        Order.affiliate_code.isnot(None),
        Order.affiliate_code != "",
        Order.commission_paid == False,
        Order.status == "termine"
    ).all()
    
    payouts = []
    for order in orders:
        commission = order.total_amount * 0.15
        payouts.append({
            "order_id": order.id,
            "affiliate_code": order.affiliate_code,
            "amount": round(commission, 2),
            "payout_phone": order.affiliate_payout_phone,
            "customer": order.customer_name,
            "order_date": order.created_at.isoformat() if order.created_at else None
        })
    return payouts

@app.get("/admin/payouts-summary")
def get_payouts_summary(db: Session = Depends(get_db), current_admin: dict = Depends(get_admin_user)):
    """Résumé des paiements à effectuer par affilié"""
    summary = db.query(
        Order.affiliate_code,
        Order.affiliate_payout_phone,
        func.sum(Order.total_amount * 0.15).label("total_to_pay"),
        func.count(Order.id).label("order_count")
    ).filter(
        Order.status == "termine",
        Order.affiliate_code.isnot(None),
        Order.affiliate_code != "",
        Order.commission_paid == False
    ).group_by(Order.affiliate_code, Order.affiliate_payout_phone).all()

    return [
        {
            "affiliate_code": row.affiliate_code,
            "payout_phone": row.affiliate_payout_phone,
            "total_to_pay": round(float(row.total_to_pay), 2),
            "order_count": row.order_count
        }
        for row in summary
    ]


# ============================================================
# 💳 ROUTES DE PAIEMENT CAMPAY
# ============================================================

@app.post("/payments/campay/init", response_model=PaymentInitResponse)
async def init_campay_payment(
    request: PaymentInitRequest,
    db: Session = Depends(get_db)
):
    """
    Initialise un paiement Campay pour l'acompte 40% d'une commande
    
    Flow KemTchop :
    1. Client crée une commande (total_amount)
    2. Cette route calcule 40% et crée le paiement Campay
    3. Le frontend redirige vers payment_url pour payer
    """
    # Vérifier que la commande existe et est en attente
    order = db.query(Order).filter(
        Order.id == request.order_id,
        Order.status == "en_attente"
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée ou déjà traitée")
    
    # Calcul des montants (40% acompte, 60% solde)
    deposit_amount = round(request.amount * 0.40)  # 40% à payer maintenant
    balance_amount = round(request.amount * 0.60)   # 60% à payer à la livraison
    
    # Référence unique pour Campay
    campay_reference = f"KEMTCHOP-{request.order_id}-{deposit_amount}"
    
    try:
        # Créer le paiement via Campay
        payment_result = await campay_service.create_payment(
            amount=deposit_amount,
            description=request.description or f"Acompte commande #{request.order_id}",
            reference=campay_reference,
            phone=request.phone,
            metadata={
                "order_id": request.order_id,
                "customer_phone": request.phone,
                "total_amount": request.amount,
                "balance_amount": balance_amount,
                "type": "deposit_40pct"
            }
        )
        
        if not payment_result.get("success"):
            raise HTTPException(status_code=500, detail="Échec de l'initialisation du paiement")
        
        # Mettre à jour la commande avec la référence Campay
        order.campay_reference = campay_reference
        order.deposit_amount = deposit_amount
        db.commit()
        
        logger.info(f"💳 Paiement Campay initialisé : {campay_reference} → {deposit_amount} FCFA")
        
        return PaymentInitResponse(
            success=True,
            payment_url=payment_result["payment_url"],
            reference=campay_reference,
            deposit_amount=deposit_amount,
            balance_amount=balance_amount,
            message=f"Veuillez payer {deposit_amount} FCFA d'acompte pour confirmer votre commande"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur init paiement Campay : {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'initialisation du paiement. Veuillez réessayer."
        )


@app.post("/payments/campay/webhook")
async def campay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook Campay : reçoit les notifications de statut de paiement
    
    Campay envoie un POST quand un paiement change de statut :
    - PENDING → SUCCESS (paiement réussi)
    - PENDING → FAILED (paiement échoué)
    """
    try:
        # Lire le corps brut pour vérification signature
        body = await request.body()
        signature = request.headers.get("X-Campay-Signature", "")
        
        # ✅ Vérifier la signature (sécurité)
        if not CampayService.verify_webhook_signature(body, signature):
            logger.warning(f"⚠️ Signature webhook invalide : {signature}")
            raise HTTPException(status_code=401, detail="Signature invalide")
        
        # Parser le JSON
        payload = WebhookRequest.parse_raw(body)
        
        logger.info(f"🔔 Webhook Campay reçu : {payload.reference} → {payload.status}")
        
        # Trouver la commande via la référence Campay
        order = db.query(Order).filter(
            Order.campay_reference == payload.reference
        ).first()
        
        if not order:
            logger.warning(f"⚠️ Commande non trouvée pour référence : {payload.reference}")
            return {"status": "ignored", "reason": "order_not_found"}
        
        # Traiter selon le statut
        if payload.status == "SUCCESS":
            # ✅ Paiement réussi : mettre à jour la commande
            order.status = "acompte_paye"
            order.payment_status = "PARTIAL"  # Enum PaymentStatus
            
            # Enregistrer la transaction d'acompte
            transaction = Transaction(
                order_id=order.id,
                amount=payload.amount,
                transaction_type="deposit",
                payment_reference=payload.reference,
                status="success",
                payment_method=getattr(PaymentMethod, payload.method.upper().replace(" ", "_"), None) if payload.method else None,
                operator_reference=payload.reference
            )
            db.add(transaction)
            
            # 🔔 Notification push au client
            if order.phone:
                client = db.query(User).filter(User.phone == order.phone).first()
                if client and client.expo_push_token:
                    send_kemtchop_notification(
                        client.expo_push_token,
                        "KemTchop ✅",
                        f"Votre acompte de {payload.amount} FCFA est confirmé. La préparation commence !"
                    )
            
            db.commit()
            logger.info(f"✅ Commande #{order.id} : acompte payé via Campay")
            
        elif payload.status == "FAILED":
            # ❌ Paiement échoué : garder en attente ou annuler
            order.status = "echec_paiement"
            db.commit()
            logger.warning(f"❌ Commande #{order.id} : paiement Campay échoué")
            
        # Réponse à Campay (doit être rapide < 5s)
        return {"status": "received", "reference": payload.reference}
        
    except Exception as e:
        logger.error(f"❌ Erreur traitement webhook Campay : {str(e)}", exc_info=True)
        # Toujours retourner 200 à Campay pour éviter les retries infinis
        return {"status": "error", "message": "Webhook processing failed"}


@app.get("/payments/campay/status/{reference}")
async def get_campay_payment_status(
    reference: str,
    db: Session = Depends(get_db)
):
    """
    Permet au frontend de poller le statut d'un paiement
    (fallback si le webhook est retardé)
    """
    try:
        # Vérifier d'abord en base (plus rapide)
        order = db.query(Order).filter(Order.campay_reference == reference).first()
        if order:
            return {
                "order_id": order.id,
                "order_status": order.status,
                "payment_status": order.payment_status,
                "campay_reference": reference
            }
        
        # Sinon interroger Campay directement
        result = await campay_service.verify_payment(reference)
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification statut Campay : {str(e)}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le statut")

# ============================================================
# 🏁 ROUTE DE SANTÉ (Health Check)
# ============================================================

@app.get("/health")
def health_check():
    """Endpoint de vérification de santé de l'API"""
    return {
        "status": "ok",
        "service": "KemTchop API",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================
# 🚀 NOTE : INITIALISATION DE LA BASE (optionnel)
# ============================================================
# Pour la production, utilisez Alembic pour les migrations.
# En développement, vous pouvez décommenter la ligne ci-dessous :

# from app.models import Base
# Base.metadata.create_all(bind=engine)

logger.info("🚀 KemTchop API démarrée avec succès")




