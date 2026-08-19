"""
PostgreSQL Migration Script
============================
Creates the `sell_transactions` table and required indexes
on the Neon PostgreSQL database.

Run:
    python migrations/migrate_postgres.py
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    print("❌  POSTGRES_URL not found in environment. Check your .env file.")
    sys.exit(1)


DDL_SELL_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS sell_transactions (
    id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),

    client_id             VARCHAR(255)  NOT NULL,
    symbol                VARCHAR(50)   NOT NULL,

    sell_date             DATE          NOT NULL,
    sell_quantity         BIGINT        NOT NULL,
    sell_price            NUMERIC(15,2) NOT NULL,

    pnl_amount            NUMERIC(15,2) NOT NULL,
    pnl_percentage        NUMERIC(10,4) NOT NULL,

    min_hold_duration     INTEGER       NOT NULL DEFAULT 0,
    max_hold_duration     INTEGER       NOT NULL DEFAULT 0,

    -- The earliest and latest buy dates among the lots consumed in this sell
    first_buy_date        DATE,
    last_buy_date         DATE,

    trade_sequence        INTEGER,
    exit_type             VARCHAR(20),
    entry_type            VARCHAR(20),

    peak_price_during_hold NUMERIC(15,2),
    mcap_category         VARCHAR(20),

    created_at            TIMESTAMP     DEFAULT NOW()
);
"""

DDL_INGESTION_STATUS = """
CREATE TABLE IF NOT EXISTS ingestion_status (
    file_hash             VARCHAR(64)   PRIMARY KEY,
    last_row_index        INTEGER       NOT NULL DEFAULT 0,
    last_processed_date   DATE,
    updated_at            TIMESTAMP     DEFAULT NOW()
);
"""

DDL_INDEXES = [
    (
        "idx_client_id",
        "CREATE INDEX IF NOT EXISTS idx_client_id ON sell_transactions(client_id);",
    ),
    (
        "idx_symbol",
        "CREATE INDEX IF NOT EXISTS idx_symbol ON sell_transactions(symbol);",
    ),
    (
        "idx_sell_date",
        "CREATE INDEX IF NOT EXISTS idx_sell_date ON sell_transactions(sell_date);",
    ),
]


def run_migration():
    print("🔌  Connecting to PostgreSQL …")
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # --- Tables --------------------------------------------------------
            print("📋  Creating table `sell_transactions` …")
            cur.execute(DDL_SELL_TRANSACTIONS)
            print("    ✅  sell_transactions ready.")

            print("📋  Creating table `ingestion_status` …")
            cur.execute(DDL_INGESTION_STATUS)
            print("    ✅  ingestion_status ready.")

            # --- Indexes -------------------------------------------------------
            for idx_name, idx_sql in DDL_INDEXES:
                print(f"🔍  Creating index `{idx_name}` …")
                cur.execute(idx_sql)
                print(f"    ✅  Index `{idx_name}` ready.")

        conn.commit()

    print("\n🎉  PostgreSQL migration completed successfully!")


if __name__ == "__main__":
    run_migration()
