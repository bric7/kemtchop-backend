import requests
import uuid

BASE_URL = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "adminpassword"

def get_auth_headers():
    print(f"🔑 Connexion en tant que {ADMIN_USER}...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        if resp.status_code != 200:
            print(f"❌ Échec auth: {resp.text}")
            return None
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"❌ Erreur de connexion au serveur: {e}")
        return None

def test_full_cycle():
    print("🚀 Démarrage du test de cycle complet KemTchop v3.0...")
    headers = get_auth_headers()
    if not headers: return

    # 1. Vérification de l'inventaire
    print("\n1. Lecture de l'inventaire actuel...")
    try:
        inv_resp = requests.get(f"{BASE_URL}/inventory/ingredients", headers=headers)
        if inv_resp.status_code == 200:
            print(f"✅ {len(inv_resp.json())} ingrédients trouvés.")
        else:
            print(f"❌ Erreur inventaire: {inv_resp.text}")
    except Exception as e:
        print(f"❌ Erreur: {e}")

    # 2. Recherche d'une production à lancer
    print("\n2. Recherche d'une production en attente (statut 'confirmed')...")
    try:
        live_resp = requests.get(f"{BASE_URL}/production/live", headers=headers)
        live_offers = live_resp.json()

        target = next((o for o in live_offers if o["status"] == "confirmed"), None)

        if not target:
            print("ℹ️ Aucune offre 'confirmed' trouvée. Test de la liste complète...")
            if live_offers:
                print(f"Statut du premier item: {live_offers[0]['status']}")
            return

        offer_id = target["id"]
        print(f"🎯 Cible trouvée: {target['product_name']} (ID: {offer_id})")

        # 3. Lancer la production
        print(f"\n3. Lancement de la production (Passage en COOKING)...")
        start_resp = requests.post(f"{BASE_URL}/production/{offer_id}/start", headers=headers)

        if start_resp.status_code == 200:
            print("✅ Statut mis à jour avec succès.")

            # 4. Vérifier les mouvements
            print("\n4. Vérification des mouvements de stock générés...")
            mvt_resp = requests.get(f"{BASE_URL}/inventory/movements", headers=headers)
            if mvt_resp.status_code == 200:
                mvts = mvt_resp.json()
                relevant = [m for m in mvts if m.get("reference_id") == offer_id]
                if relevant:
                    print(f"✨ SUCCÈS: {len(relevant)} mouvements de stock créés pour cette production.")
                else:
                    print("⚠️ Aucun mouvement trouvé. Vérifiez si le produit a une recette configurée.")
        else:
            print(f"❌ Échec du lancement: {start_resp.text}")

    except Exception as e:
        print(f"❌ Erreur durant le cycle: {e}")

if __name__ == "__main__":
    test_full_cycle()
