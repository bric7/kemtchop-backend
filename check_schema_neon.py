import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("--- daily_offers columns ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'daily_offers'")
    cols = cur.fetchall()
    for c in cols:
        print(f"{c[0]}: {c[1]}")

    print("\n--- reels columns ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'reels'")
    cols = cur.fetchall()
    for c in cols:
        print(f"{c[0]}: {c[1]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
