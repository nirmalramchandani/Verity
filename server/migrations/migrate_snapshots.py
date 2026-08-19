"""
PostgreSQL Migration Script — Snapshots
=======================================
Creates the `investor_snapshots` table on the Neon PostgreSQL database.
This table stores the end-of-month flattened metrics for each investor.

Run:
    python migrations/migrate_snapshots.py
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    print("[ERROR] POSTGRES_URL not found in environment.")
    sys.exit(1)


DDL_TABLE = """
CREATE TABLE IF NOT EXISTS investor_snapshots (
    id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    
    investor_id           VARCHAR(255)  NOT NULL,
    snapshot_date         DATE          NOT NULL,
    
    -- Ranking Scores
    smart_money_score     NUMERIC(5,2),
    consistency_score     NUMERIC(5,2),
    conviction_score      NUMERIC(5,2),
    risk_management_score NUMERIC(5,2),
    
    -- Performance Metrics
    total_trades          INTEGER,
    win_rate              NUMERIC(5,4),
    avg_return_pct        NUMERIC(10,2),
    profit_factor         NUMERIC(10,2),
    max_drawdown_pct      NUMERIC(10,2),
    total_realized_pnl    NUMERIC(15,2),
    
    -- Conviction & Activity
    active_positions      INTEGER,
    avg_hold_days         NUMERIC(10,2),
    
    -- Behavioral DNA
    entry_style           VARCHAR(50),
    exit_style            VARCHAR(50),
    preferred_mcap        VARCHAR(50),
    favorite_sector       VARCHAR(50),
    
    created_at            TIMESTAMP     DEFAULT NOW(),
    
    -- Ensure exactly 1 snapshot per investor per date
    UNIQUE(investor_id, snapshot_date)
);
"""

def run_migration():
    print("[*] Connecting to PostgreSQL...")
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            print("[*] Creating table `investor_snapshots`...")
            cur.execute(DDL_TABLE)
            print("    [OK] Table ready.")
        conn.commit()
    print("\n[DONE] Snapshot migration completed successfully!")

if __name__ == "__main__":
    run_migration()
