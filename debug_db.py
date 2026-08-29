
import os
from sqlalchemy import create_engine, inspect, text

DATABASE_URL = "postgresql://neondb_owner:npg_hGQT09SEqDCL@ep-purple-dream-an4gl1ei.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)

def debug():
    with engine.connect() as conn:
        print("--- Schemas ---")
        result = conn.execute(text("SELECT schema_name FROM information_schema.schemata;"))
        for row in result:
            print(f"Schema: {row[0]}")

        inspector = inspect(engine)
        schemas = inspector.get_schema_names()
        for schema in schemas:
            print(f"\n--- Tables in schema: {schema} ---")
            tables = inspector.get_table_names(schema=schema)
            print(tables)

        print("\n--- Types (Enums) ---")
        result = conn.execute(text("SELECT n.nspname as schema, t.typname as name FROM pg_type t LEFT JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typtype = 'e';"))
        for row in result:
            print(f"Enum: {row[0]}.{row[1]}")

        print("\n--- Alembic Version ---")
        try:
            result = conn.execute(text("SELECT version_num FROM alembic_version;"))
            for row in result:
                print(f"Current version: {row[0]}")
        except Exception as e:
            print(f"Could not read alembic_version: {e}")

        print("\n--- Current Search Path ---")
        result = conn.execute(text("SHOW search_path;"))
        for row in result:
            print(f"search_path: {row[0]}")

if __name__ == "__main__":
    debug()
