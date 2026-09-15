import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_vMsSTmy4Pql6@ep-autumn-forest-alejvkl5.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("--- daily_offers columns ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'daily_offers'")
    cols = cur.fetchall()
    for c in cols:
        print(f"{c[0]}: {c[1]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
