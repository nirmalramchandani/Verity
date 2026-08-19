"""
Monthly Snapshot Ingestor
=========================
Pulls current investor state and metrics from MongoDB Atlas and
pushes a flattened snapshot row into PostgreSQL `investor_snapshots`.

Usage:
    python scripts/monthly_snapshot.py

Intended to run via CRON on the last day of the month.
Uses ON CONFLICT DO UPDATE so it is safe to rerun multiple times on the same date.
"""

import os
import sys
from datetime import date
from dotenv import load_dotenv

# Add project root to sys.path so we can import from db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import investors_collection, investor_metrics_collection
from db.postgres import get_connection

def generate_monthly_snapshots(target_date: date = None):
    if target_date is None:
        target_date = date.today()
        
    print(f"[*] Generating investor snapshots for date: {target_date}")
    
    # 1. Fetch all investors
    investors = list(investors_collection.find({}))
    if not investors:
        print("[-] No investors found in MongoDB. Exiting.")
        return
        
    print(f"[*] Found {len(investors)} investors. Fetching metrics...")
    
    snapshot_records = []
    
    # 2. Build flat records
    for inv in investors:
        inv_id = inv["_id"]
        
        # Rankings (from hot doc)
        rankings = inv.get("ranking_scores", {})
        behavior = inv.get("behavioral_dna", {})
        activity = inv.get("activity_metrics", {})
        
        # Metrics (from cold doc)
        metrics_doc = investor_metrics_collection.find_one({"investor_id": inv_id}) or {}
        perf = metrics_doc.get("performance_metrics", {})
        convic = metrics_doc.get("conviction_metrics", {})
        
        record = (
            inv_id,
            target_date,
            
            # Rankings
            rankings.get("smart_money_score"),
            rankings.get("consistency_score"),
            rankings.get("conviction_score"),
            rankings.get("risk_management_score"),
            
            # Performance
            perf.get("total_trades"),
            perf.get("win_rate"),
            perf.get("avg_return_pct"),
            perf.get("profit_factor"),
            perf.get("max_drawdown_pct"),
            perf.get("total_realized_pnl"),
            
            # Conviction & Activity
            activity.get("active_positions"),
            convic.get("avg_hold_days"),
            
            # Behavioral
            behavior.get("entry_style"),
            behavior.get("exit_style"),
            behavior.get("preferred_mcap"),
            behavior.get("favorite_sector")
        )
        
        snapshot_records.append(record)
        
    # 3. Upsert to Postgres
    print(f"[*] Upserting {len(snapshot_records)} records to PostgreSQL...")
    
    upsert_query = """
        INSERT INTO investor_snapshots (
            investor_id, snapshot_date,
            smart_money_score, consistency_score, conviction_score, risk_management_score,
            total_trades, win_rate, avg_return_pct, profit_factor, max_drawdown_pct, total_realized_pnl,
            active_positions, avg_hold_days,
            entry_style, exit_style, preferred_mcap, favorite_sector
        ) VALUES (
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (investor_id, snapshot_date) DO UPDATE SET
            smart_money_score = EXCLUDED.smart_money_score,
            consistency_score = EXCLUDED.consistency_score,
            conviction_score = EXCLUDED.conviction_score,
            risk_management_score = EXCLUDED.risk_management_score,
            
            total_trades = EXCLUDED.total_trades,
            win_rate = EXCLUDED.win_rate,
            avg_return_pct = EXCLUDED.avg_return_pct,
            profit_factor = EXCLUDED.profit_factor,
            max_drawdown_pct = EXCLUDED.max_drawdown_pct,
            total_realized_pnl = EXCLUDED.total_realized_pnl,
            
            active_positions = EXCLUDED.active_positions,
            avg_hold_days = EXCLUDED.avg_hold_days,
            
            entry_style = EXCLUDED.entry_style,
            exit_style = EXCLUDED.exit_style,
            preferred_mcap = EXCLUDED.preferred_mcap,
            favorite_sector = EXCLUDED.favorite_sector,
            
            created_at = NOW();
    """
    
    prune_query = """
        -- Delete non-December snapshots older than 1 year to save storage
        DELETE FROM investor_snapshots 
        WHERE snapshot_date < CURRENT_DATE - INTERVAL '1 year' 
          AND EXTRACT(MONTH FROM snapshot_date) != 12;
    """
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(upsert_query, snapshot_records)
            print("[*] Pruning old non-yearly snapshots to save NeonDB storage...")
            cur.execute(prune_query)
        conn.commit()
        
    print("[DONE] Snapshot generation and pruning complete.")

if __name__ == "__main__":
    generate_monthly_snapshots()
