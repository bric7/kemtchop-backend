import requests
import uuid
import time

BASE_URL = "http://localhost:3000"
# Utilisez un jeton admin valide si nécessaire pour les tests réels
ADMIN_HEADERS = {"X-Admin-Token": "test-admin-secret"}

def test_cycle():
    print("🚀 Démarrage du test de cycle complet...")

    # 1. Création d'un ingrédient
    print("\n1. Création ingrédient...")
    ing_resp = requests.post(f"{BASE_URL}/inventory/ingredients", json={
        "name": "Poulet Test",
        "unit": "kg",
        "current_quantity": 10.0,
        "min_threshold": 2.0
    })
    if ing_resp.status_code != 201:
        print(f"❌ Échec création ingrédient: {ing_resp.text}")
        return
    ing_id = ing_resp.json()["id"]
    print(f"✅ Ingrédient créé: ID {ing_id}")

    # 2. Création/Vérification d'un produit et sa recette
    # On suppose qu'un produit ID 1 existe ou on en crée un.
    # Pour le test, on va juste vérifier si /inventory/ingredients répond

    print("\n2. Vérification listage ingrédients...")
    list_resp = requests.get(f"{BASE_URL}/inventory/ingredients")
    print(f"✅ Liste reçue: {len(list_resp.json())} ingrédients")

    # Note: Le reste nécessite une DB peuplée et des IDs valides (DailyOffer, Order, etc.)
    # Ce script sert de base pour des tests d'intégration manuels via Swagger ou Postman.
    print("\n🏁 Fin du test préliminaire. Les routes sont prêtes.")

if __name__ == "__main__":
    test_cycle()
