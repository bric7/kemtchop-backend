import requests
import urllib3

# Désactiver les avertissements SSL au cas où le certificat du VPS n'est pas reconnu localement
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ 1. MODIFIER ICI : L'URL de ton backend hébergé sur Coolify
BASE_URL = "https://api.kemtchop.shop"

# ✅ 2. Tes identifiants admin (le téléphone et le mot de passe)
ADMIN_PHONE = "600000000"
ADMIN_PASS = "adminpassword"  # ⚠️ Remplace "admin" par ton vrai mot de passe admin

def get_auth_headers():
    print(f"🔑 Connexion en tant que {ADMIN_PHONE}...")
    try:
        # Le endpoint de login est /users/login et attend "phone" et "password"
        resp = requests.post(f"{BASE_URL}/users/login", json={
            "phone": ADMIN_PHONE,
            "password": ADMIN_PASS
        })
        
        if resp.status_code != 200:
            print(f"❌ Échec de l'authentification: {resp.status_code} - {resp.text}")
            return None
            
        token = resp.json()["access_token"]
        print("✅ Connexion réussie ! Token obtenu.")
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"❌ Erreur de connexion au serveur: {e}")
        return None

def test_full_cycle():
    print("\n🚀 Démarrage du test de cycle complet KemTchop v3.0...")
    headers = get_auth_headers()
    if not headers: 
        print("🛑 Arrêt du test car la connexion a échoué.")
        return

    # 1. Vérification des offres en direct
    print("\n1. Recherche d'une production à lancer (statut 'confirmed')...")
    try:
        live_resp = requests.get(f"{BASE_URL}/production/live", headers=headers)
        
        if live_resp.status_code != 200:
            print(f"❌ Erreur lecture production: {live_resp.status_code} - {live_resp.text}")
            return
            
        live_offers = live_resp.json()
        print(f"ℹ️ {len(live_offers)} production(s) active(s) trouvée(s).")

        # Chercher une offre confirmée
        target = next((o for o in live_offers if o["status"] == "confirmed"), None)

        if not target:
            print("⚠️ Aucune offre avec le statut 'confirmed' trouvée pour le moment.")
            print("💡 Conseil : Dans l'admin, crée une offre pour aujourd'hui et clique sur '✅ Forcer Prod.', puis relance ce test.")
            return

        offer_id = target["id"]
        print(f"🎯 Cible trouvée: {target['product_name']} (ID: {offer_id})")

        # 2. Lancer la production
        print(f"\n2. Lancement de la production (Passage en COOKING)...")
        start_resp = requests.post(f"{BASE_URL}/production/{offer_id}/start", headers=headers)

        if start_resp.status_code == 200:
            print("✅ Statut mis à jour avec succès !")
            print(f"📝 Réponse du serveur: {start_resp.json()}")
        else:
            print(f"❌ Échec du lancement: {start_resp.status_code} - {start_resp.text}")

    except Exception as e:
        print(f"❌ Erreur durant le cycle: {e}")

if __name__ == "__main__":
    test_full_cycle()