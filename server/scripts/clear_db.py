import os
import sys
from dotenv import load_dotenv

# Add backend dir to path so db imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.postgres import get_connection
from db.mongo import investors_collection, investor_metrics_collection

def clear_databases():
    print("Clearing MongoDB collections...")
    try:
        investors_collection.delete_many({})
        investor_metrics_collection.delete_many({})
        print("✅ MongoDB collections ('investors', 'investor_metrics') cleared.")
    except Exception as e:
        print(f"❌ Error clearing MongoDB: {e}")

    print("\nClearing PostgreSQL tables...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE sell_transactions RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE TABLE ingestion_status RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE TABLE investor_snapshots RESTART IDENTITY CASCADE;")
            conn.commit()
        print("✅ PostgreSQL tables ('sell_transactions', 'ingestion_status', 'investor_snapshots') cleared.")
    except Exception as e:
        print(f"❌ Error clearing PostgreSQL: {e}")

if __name__ == "__main__":
    clear_databases()
