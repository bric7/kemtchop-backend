
import sys
import os
sys.path.append(os.getcwd())

try:
    from app.database import SessionLocal, engine
    from app.entities.order import Order
    from sqlalchemy import text

    db = SessionLocal()
    # Check if we can query the orders table
    count = db.query(Order).count()
    print(f"✅ Database connection successful. Order count: {count}")

    # Check UUID type
    res = db.execute(text("SELECT id FROM orders LIMIT 1")).fetchone()
    if res:
        print(f"✅ Order ID sample: {res[0]} (Type: {type(res[0])})")
    else:
        print("ℹ️ No orders found to verify UUID type.")

    db.close()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
