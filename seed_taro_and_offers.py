import sqlite3
import uuid
from datetime import date

conn = sqlite3.connect("dev-fallback.db")
cursor = conn.cursor()

today_str = date.today().isoformat()
print(f"Date du jour: {today_str}")

# 1. Vérifier si le produit "Taro Sauce Jaune" existe dans products, sinon le créer
cursor.execute("SELECT id, name FROM products WHERE name LIKE '%Taro%';")
taro_product = cursor.fetchone()

if not taro_product:
    print("➕ Création du produit 'Taro Sauce Jaune' dans products")
    cursor.execute("""
        INSERT INTO products (name, description, category, price, complements)
        VALUES ('Taro Sauce Jaune', 'Taro Sauce Jaune authentique du pays', 'Traditionnel', 3000.0, 'Sauce jaune, Viande de boeuf, Peau de boeuf')
    """)
    conn.commit()
    cursor.execute("SELECT id, name FROM products WHERE name LIKE '%Taro%';")
    taro_product = cursor.fetchone()

taro_id = taro_product[0]
print(f"✅ Produit Taro trouvé/créé: ID={taro_id}, Nom={taro_product[1]}")

# 2. Vérifier/Créer l'offre du jour (DailyOffer) pour Taro à aujourd'hui
cursor.execute("SELECT id, target_date FROM daily_offers WHERE product_id = ? AND target_date = ?;", (taro_id, today_str))
taro_offer = cursor.fetchone()

if not taro_offer:
    offer_id = str(uuid.uuid4())
    print(f"➕ Création de l'offre DailyOffer du jour pour Taro (ID={offer_id}, target_date={today_str})")
    cursor.execute("""
        INSERT INTO daily_offers (id, product_id, target_date, minimum_threshold, max_capacity, price_per_unit, current_revenue, reserved_portions, status, created_at, updated_at)
        VALUES (?, ?, ?, 4, 20, 3000.0, 0.0, 1, 'proposed', datetime('now'), datetime('now'))
    """, (offer_id, taro_id, today_str))
    conn.commit()
else:
    offer_id = taro_offer[0]
    print(f"✅ Offre DailyOffer existante pour Taro: ID={offer_id}")

# 3. Mettre à jour le Reel du Taro pour le lier à cette DailyOffer
cursor.execute("UPDATE reels SET daily_offer_id = ? WHERE title LIKE '%Taro%' OR product_name LIKE '%Taro%';", (offer_id,))
conn.commit()

# 4. Vérifier les Reels mis à jour
cursor.execute("SELECT id, title, product_name, daily_offer_id FROM reels;")
print("--- État des Reels après mise à jour ---")
for r in cursor.fetchall():
    print(r)

conn.close()
