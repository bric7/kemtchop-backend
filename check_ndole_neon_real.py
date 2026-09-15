import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_vMsSTmy4Pql6@ep-autumn-forest-alejvkl5.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("--- Products ---")
    cur.execute("SELECT id, name, video_url, image_url FROM products WHERE name ILIKE '%Ndole%'")
    product = cur.fetchone()
    if product:
        print(f"Product: {product[1]} (ID: {product[0]}), Video: {product[2]}, Image: {product[3]}")
        p_id = product[0]

        print("\n--- Daily Offers for today ---")
        cur.execute("SELECT id, target_date, status FROM daily_offers WHERE product_id = %s AND target_date = '2026-09-15'", (p_id,))
        offers = cur.fetchall()
        for o in offers:
            print(f"Offer ID: {o[0]}, Date: {o[1]}, Status: {o[2]}")
    else:
        print("Product NDOLE not found.")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
