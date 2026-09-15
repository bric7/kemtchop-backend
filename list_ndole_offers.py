import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_vMsSTmy4Pql6@ep-autumn-forest-alejvkl5.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, target_date, status FROM daily_offers WHERE product_id = 1")
    offers = cur.fetchall()
    print(f"Found {len(offers)} offers for Ndole:")
    for o in offers:
        print(f"ID: {o[0]}, Date: {o[1]}, Status: {o[2]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
