
import os
import sys

# Set DATABASE_URL before importing app modules
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

sys.path.append(os.getcwd())

try:
    from app.database import SessionLocal
    from app.entities.product import Product
    from app.entities.order import Order
    from app.entities.user import User

    from app.database import SessionLocal, engine
    db = SessionLocal()

    print("--- Running Integration Tests ---")
    print(f"Engine URL: {engine.url}")

    # 0. List tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    print(f"Existing tables: {inspector.get_table_names()}")

    # 1. Test Products
    product_count = db.query(Product).count()
    print(f"✅ Product list access: {product_count} products found.")

    # 2. Test Users
    user_count = db.query(User).count()
    print(f"✅ User list access: {user_count} users found.")

    # 3. Test Orders (UUID check)
    order = db.query(Order).first()
    if order:
        print(f"✅ Order access successful. ID: {order.id} (Type: {type(order.id)})")
    else:
        print("ℹ️ No orders found in database.")

    print("--- All core entity access tests passed ---")
    db.close()

except Exception as e:
    print(f"❌ Integration Test Failed: {e}")
    import traceback
    traceback.print_exc()
