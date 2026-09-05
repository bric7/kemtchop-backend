import os
import psycopg2
import uuid
from datetime import date

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

today_str = date.today().isoformat()
print(f"📡 Connexion à la base Neon PostgreSQL... (Date cible: {today_str})")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# 1. Lister les colonnes de la table reels
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'reels';")
print("Colonnes table reels:", cursor.fetchall())

# 2. Chercher le produit Taro
cursor.execute("SELECT id, name FROM products WHERE name ILIKE '%Taro%';")
taro_product = cursor.fetchone()

if not taro_product:
    print("➕ Création du produit 'Taro Sauce Jaune' sur Neon")
    cursor.execute("""
        INSERT INTO products (name, description, category, price, complements)
        VALUES ('Taro Sauce Jaune', 'Taro Sauce Jaune authentique du pays', 'Traditionnel', 3000.0, 'Sauce jaune, Viande de boeuf, Peau de boeuf')
        RETURNING id, name;
    """)
    taro_product = cursor.fetchone()
    conn.commit()

taro_id, taro_name = taro_product
print(f"✅ Produit Taro: ID={taro_id}, Nom={taro_name}")

# 3. Vérifier/Créer l'offre DailyOffer du jour pour Taro
cursor.execute("SELECT id, target_date, status FROM daily_offers WHERE product_id = %s AND target_date = %s;", (taro_id, today_str))
taro_offer = cursor.fetchone()

if not taro_offer:
    offer_id = str(uuid.uuid4())
    print(f"➕ Création de l'offre DailyOffer du jour pour Taro sur Neon (ID={offer_id}, Date={today_str})")
    cursor.execute("""
        INSERT INTO daily_offers (id, product_id, target_date, minimum_threshold, max_capacity, price_per_unit, current_revenue, reserved_portions, status, created_at, updated_at)
        VALUES (%s, %s, %s, 4, 20, 3000.0, 0.0, 1, 'proposed', NOW(), NOW())
        RETURNING id;
    """, (offer_id, taro_id, today_str))
    conn.commit()
    print("✅ Offre DailyOffer créée sur Neon.")
else:
    offer_id = taro_offer[0]
    print(f"✅ Offre DailyOffer déjà existante sur Neon: ID={offer_id}, Statut={taro_offer[2]}")

# 4. Vérifier et insérer/mettre à jour dans reels
cursor.execute("SELECT id, title, product_name, daily_offer_id FROM reels WHERE title ILIKE '%Taro%' OR product_name ILIKE '%Taro%';")
reels_taro = cursor.fetchall()
print(f"Reels Taro existants: {reels_taro}")

if reels_taro:
    cursor.execute(
        "UPDATE reels SET daily_offer_id = %s WHERE id = %s;",
        (str(offer_id), 1)
    )
    conn.commit()
    print("✅ Reel Taro mis à jour avec le daily_offer_id.")
else:
    cursor.execute("""
        INSERT INTO reels (title, product_name, daily_offer_id, category, price, is_active, priority)
        VALUES ('Taro Sauce Jaune authentique', %s, %s, 'Traditionnel', 3000.0, TRUE, 10);
    """, (taro_name, offer_id))
    conn.commit()
    print("✅ Nouveau Reel Taro inséré.")

# 5. Afficher un récapitulatif
cursor.execute("""
    SELECT d.id, p.name, d.target_date, d.status, d.price_per_unit, d.reserved_portions
    FROM daily_offers d
    JOIN products p ON d.product_id = p.id
    WHERE d.target_date = %s;
""", (today_str,))
print("\n--- DailyOffers actives pour aujourd'hui sur Neon ---")
for row in cursor.fetchall():
    print(f"🍽️ {row[1]} | Date: {row[2]} | Statut: {row[3]} | Prix: {row[4]} F | Réservations: {row[5]}")

conn.close()
print("\n✨ Synchronisation Neon terminée avec succès !")
