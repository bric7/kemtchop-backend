import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_vMsSTmy4Pql6@ep-autumn-forest-alejvkl5.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT p.name, p.video_url, d.video_url
        FROM daily_offers d
        JOIN products p ON d.product_id = p.id
        WHERE d.id = 'ed0e2c4b-2093-4d2c-8ca3-65cdb6fdc759'
    """)
    res = cur.fetchone()
    if res:
        print(f"Product: {res[0]}, P-Video: {res[1]}, O-Video: {res[2]}")
    else:
        print("Offer not found.")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
