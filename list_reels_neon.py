import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, title, video_url, image_url, daily_offer_id FROM reels")
    reels = cur.fetchall()
    print(f"Found {len(reels)} explicit reels:")
    for r in reels:
        print(f"ID: {r[0]}, Title: {r[1]}, Video: {r[2]}, Image: {r[3]}, OfferID: {r[4]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
