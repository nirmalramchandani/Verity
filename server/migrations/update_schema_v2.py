import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("POSTGRES_URL")

def update_schema():
    print("🔌 Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    columns_to_add = [
        ("first_buy_date", "DATE"),
        ("last_buy_date", "DATE"),
        ("trade_sequence", "INTEGER"),
        ("exit_type", "VARCHAR(20)"),
        ("entry_type", "VARCHAR(20)"),
        ("peak_price_during_hold", "NUMERIC(15,2)"),
        ("mcap_category", "VARCHAR(20)")
    ]

    for col_name, col_type in columns_to_add:
        try:
            print(f"Adding column {col_name}...")
            cur.execute(f"ALTER TABLE sell_transactions ADD COLUMN {col_name} {col_type};")
            print(f"✅ Column {col_name} added.")
        except psycopg2.errors.DuplicateColumn:
            print(f"ℹ️ Column {col_name} already exists.")
        except Exception as e:
            print(f"❌ Error adding {col_name}: {e}")

    print("\n🔍 Current columns in sell_transactions:")
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'sell_transactions';")
    cols = cur.fetchall()
    for col in cols:
        print(f" - {col[0]}")

    cur.close()
    conn.close()
    print("\n🎉 Schema update complete!")

if __name__ == "__main__":
    update_schema()
