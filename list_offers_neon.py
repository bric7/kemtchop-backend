import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT d.id, p.name, d.target_date, d.status, p.video_url, d.video_url
        FROM daily_offers d
        JOIN products p ON d.product_id = p.id
    """)
    offers = cur.fetchall()
    print(f"Found {len(offers)} offers:")
    for o in offers:
        print(f"ID: {o[0]}, Product: {o[1]}, Date: {o[2]}, Status: {o[3]}, P-Video: {o[4]}, O-Video: {o[5]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
