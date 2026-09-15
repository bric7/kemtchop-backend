import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_vMsSTmy4Pql6@ep-autumn-forest-alejvkl5.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("--- Products ---")
    cur.execute("SELECT id, name, video_url, image_url FROM products WHERE name ILIKE '%Ndole%'")
    product = cur.fetchone()
    if product:
        print(f"Product: {product[1]} (ID: {product[0]}), Video: {product[2]}, Image: {product[3]}")
    else:
        print("Product NDOLE not found.")

    print("\n--- Daily Offers ---")
    # On vérifie si la colonne video_url existe d'abord pour éviter l'erreur
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'daily_offers' AND column_name = 'video_url'")
    has_video_col = cur.fetchone() is not None

    query = "SELECT id, target_date, status" + (", video_url" if has_video_col else "") + " FROM daily_offers"
    cur.execute(query)
    offers = cur.fetchall()
    for o in offers:
        print(f"Offer: {o}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
