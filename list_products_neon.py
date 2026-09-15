import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, name, video_url FROM products")
    products = cur.fetchall()
    print(f"Found {len(products)} products:")
    for p in products:
        print(f"ID: {p[0]}, Name: {p[1]}, Video: {p[2]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
