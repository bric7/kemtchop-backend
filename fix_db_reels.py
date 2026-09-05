import sqlite3
import uuid
from datetime import date

conn = sqlite3.connect("dev-fallback.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(reels);")
columns = [col[1] for col in cursor.fetchall()]
if "daily_offer_id" not in columns:
    cursor.execute("ALTER TABLE reels ADD COLUMN daily_offer_id TEXT;")
    conn.commit()

cursor.execute("SELECT id, name FROM products;")
products = cursor.fetchall()
print("Produits en base:", products)

today_str = date.today().isoformat()

for p in products:
    p_id, p_name = p
    cursor.execute("SELECT id FROM daily_offers WHERE product_id = ? AND target_date = ?;", (p_id, today_str))
    offer = cursor.fetchone()

    if not offer:
        offer_id = str(uuid.uuid4())
        print(f"➕ Création DailyOffer pour {p_name} ({today_str})")
        cursor.execute("""
            INSERT INTO daily_offers (id, product_id, target_date, minimum_threshold, max_capacity, price_per_unit, current_revenue, reserved_portions, status, created_at, updated_at)
            VALUES (?, ?, ?, 4, 20, 2500, 0.0, 1, 'proposed', datetime('now'), datetime('now'))
        """, (offer_id, p_id, today_str))
        conn.commit()
    else:
        offer_id = offer[0]

    cursor.execute("UPDATE reels SET daily_offer_id = ? WHERE product_name = ? OR title LIKE ?;", (offer_id, p_name, f"%{p_name}%"))
    conn.commit()

print("✨ Base de données mise à jour avec succès !")
conn.close()
