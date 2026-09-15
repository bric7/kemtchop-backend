import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_vMsSTmy4Pql6@ep-autumn-forest-alejvkl5.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, product_id, target_date, status FROM daily_offers WHERE id = '3f5bf697-78da-4992-be96-217583c21b85'")
    offer = cur.fetchone()
    if offer:
        print(f"Offer: {offer}")
        p_id = offer[1]
        cur.execute("SELECT name, video_url FROM products WHERE id = %s", (p_id,))
        p = cur.fetchone()
        print(f"Product: {p}")
    else:
        print("Offer not found.")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
