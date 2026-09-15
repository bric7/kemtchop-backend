import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("--- Products ---")
    cur.execute("SELECT id, name, video_url FROM products WHERE name ILIKE '%Ndole%'")
    product = cur.fetchone()
    if product:
        print(f"Product: {product[1]} (ID: {product[0]}), Video: {product[2]}")
        p_id = product[0]

        print("\n--- Daily Offers for this product ---")
        cur.execute("SELECT id, target_date, status, video_url FROM daily_offers WHERE product_id = %s", (p_id,))
        offers = cur.fetchall()
        for o in offers:
            print(f"Offer ID: {o[0]}, Date: {o[1]}, Status: {o[2]}, Video: {o[3]}")
    else:
        print("Product NDOLE not found.")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
