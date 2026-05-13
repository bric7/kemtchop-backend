from app.database import SessionLocal
from app.models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

def fix_user(username_target, new_password):
    print(f"--- 🛠 Réparation de l'utilisateur : {username_target} ---")
    user = db.query(User).filter(User.username == username_target).first()
    
    if user:
        # 1. On hache le mot de passe
        user.hashed_password = pwd_context.hash(new_password)
        
        # 2. On répare le champ phone s'il est à None pour éviter l'erreur 500
        if user.phone is None:
            user.phone = "000000000" 
            
        db.commit()
        print(f"✅ Succès : '{username_target}' est prêt. Mot de passe haché et téléphone corrigé.")
    else:
        print(f"❌ Erreur : L'utilisateur '{username_target}' n'existe pas en base.")

if __name__ == "__main__":
    try:
        # On répare Sandra
        fix_user("sandra", "sandra12345")
    finally:
        db.close()