import psycopg2
import os

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT version_num FROM alembic_version")
    version = cur.fetchone()
    print(f"Current Alembic version on Neon: {version[0] if version else 'None'}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
