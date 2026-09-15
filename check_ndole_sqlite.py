import sqlite3

try:
    conn = sqlite3.connect("dev-fallback.db")
    cur = conn.cursor()

    print("--- Products ---")
    cur.execute("SELECT id, name, video_url FROM products WHERE name LIKE '%Ndole%'")
    products = cur.fetchall()
    for p in products:
        print(f"Product: {p[1]} (ID: {p[0]}), Video: {p[2]}")

    print("\n--- All Daily Offers ---")
    cur.execute("SELECT d.id, p.name, d.target_date, d.status FROM daily_offers d JOIN products p ON d.product_id = p.id")
    offers = cur.fetchall()
    for o in offers:
        print(f"Offer ID: {o[0]}, Product: {o[1]}, Date: {o[2]}, Status: {o[3]}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
