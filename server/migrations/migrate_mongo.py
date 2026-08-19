"""
MongoDB Migration Script
=========================
Sets up the `smart_money` database with two linked collections:

  1. investors          — identity, portfolio state, activity, ranking scores
  2. investor_metrics   — heavy analytics (performance, conviction,
                          consistency, behavioral DNA)

Both collections are linked via `investor_id` (_id in investors).

Why split?
----------
A single investor document can grow very large as positions / lots
accumulate and metrics are back-filled. Keeping hot operational data
(portfolio state, rankings) in `investors` and cold analytical data
in `investor_metrics` avoids document bloat and keeps reads fast.

Indexes created:
  investors         → last_activity.last_trade_date
                    → ranking_scores.smart_money_score
                    → behavioral_dna.favorite_sector   (text-search friendly)
  investor_metrics  → investor_id  (FK-style lookup)

Run:
    python migrations/migrate_mongo.py
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("[ERROR] MONGO_URI not found in environment. Check your .env file.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Sample seed document — INVESTORS (core / hot data)
# ---------------------------------------------------------------------------
SAMPLE_INVESTOR = {
    "_id": "ICICI_PRU_MF",

    # --- Who is this investor? ---
    "identity": {
        "name": "ICICI Prudential Mutual Fund",
        "aliases": ["ICICI PRUDENTIAL MF", "ICICI PRU MF"],
        "investor_type": "MUTUAL_FUND",       # MUTUAL_FUND | FII | DII | PROMOTER | RETAIL
        "first_seen_date": "2006-02-01",
        "last_activity_date": "2026-03-03",
    },

    # --- Live portfolio snapshot ---
    "portfolio_state": {
        "tracked_value": 15_200_000,

        # Aggregated position per symbol
        "positions": [
            {
                "symbol": "TCS",
                "qty": 500,
                "avg_price": 3100.00,
                "first_buy_date": "2024-01-01",
                "last_buy_date": "2024-06-12",
                "position_weight": 0.14,      # fraction of tracked_value
            }
        ],

        # Individual FIFO lots (used for PnL / hold-duration calculations)
        "open_lots": [
            {
                "symbol": "TCS",
                "qty": 200,
                "price": 3050.00,
                "buy_date": "2024-05-01",
            },
            {
                "symbol": "TCS",
                "qty": 300,
                "price": 3150.00,
                "buy_date": "2024-06-12",
            },
        ],
    },

    # --- High-level scores (frequently queried → stay in this doc) ---
    "ranking_scores": {
        "smart_money_score": 87.4,
        "consistency_score": 82.3,
        "conviction_score": 90.2,
        "risk_management_score": 79.5,
    },

    # --- Quick activity summary (frequently queried) ---
    "activity_metrics": {
        "last_trade_date": "2026-03-03",
        "last_buy_date": "2026-02-20",
        "active_positions": 8,
        "total_positions_traded": 142,
    },

    # --- Behavioral fingerprint (queried for filtering / screeners) ---
    "behavioral_dna": {
        "entry_style": "STAGGERED",          # LUMP_SUM | STAGGERED
        "exit_style": "GRADUAL",             # ALL_AT_ONCE | GRADUAL
        "dip_buying_score": 0.64,
        "trend_following_score": 0.81,
        "preferred_mcap": "SMALL_CAP",       # LARGE_CAP | MID_CAP | SMALL_CAP | MULTI_CAP
        "favorite_sector": "IT",
        "avg_add_on_buy": 2.4,
        "avg_reduce_on_sell": 1.2,
    },

    "metadata": {
        "created_at": "2026-03-03",
        "last_updated": "2026-03-03",
    },
}


# ---------------------------------------------------------------------------
# Sample seed document — INVESTOR_METRICS (analytics / cold data)
# Linked to investors._id via investor_id
# ---------------------------------------------------------------------------
SAMPLE_INVESTOR_METRICS = {
    # Link back to the parent investor document
    "investor_id": "ICICI_PRU_MF",

    # --- Trade-level stats ---
    "performance_metrics": {
        "total_trades": 242,
        "winning_trades": 152,
        "losing_trades": 90,
        "win_rate": 0.62,
        "avg_return_pct": 13.4,
        "median_return_pct": 8.1,
        "profit_factor": 2.1,
        "expectancy": 5.6,
        "avg_profit_pct": 21.3,
        "avg_loss_pct": -9.2,
        "max_drawdown_pct": -18.4,
        "total_realized_pnl": 4_200_000,
    },

    # --- Position-sizing discipline ---
    "conviction_metrics": {
        "avg_position_size_pct": 0.11,
        "max_position_size_pct": 0.34,
        "avg_scale_in_count": 2.3,
        "avg_scale_out_count": 1.4,
        "avg_hold_days": 380,
        "median_hold_days": 210,
        "long_hold_ratio": 0.42,
    },

    # --- Year-over-year consistency ---
    "consistency_metrics": {
        "profitable_years": 14,
        "loss_years": 4,
        "longest_win_streak": 9,
        "longest_loss_streak": 3,
        "rolling_sharpe_ratio": 1.8,
        "rolling_sortino_ratio": 2.3,
    },

    "metadata": {
        "created_at": "2026-03-03",
        "last_updated": "2026-03-03",
    },
}


# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------
INVESTORS_INDEXES = [
    # Scalar indexes
    IndexModel([("activity_metrics.last_trade_date", DESCENDING)],
               name="idx_last_trade_date"),
    IndexModel([("ranking_scores.smart_money_score", DESCENDING)],
               name="idx_smart_money_score"),
    # Sector filtering / screener queries
    IndexModel([("behavioral_dna.favorite_sector", ASCENDING)],
               name="idx_favorite_sector"),
]

INVESTOR_METRICS_INDEXES = [
    # FK-style lookup: investor_metrics where investor_id = X
    IndexModel([("investor_id", ASCENDING)],
               name="idx_investor_id"),
]


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------
def run_migration():
    print("[*] Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client["smart_money"]

    # ---- investors collection ------------------------------------------------
    print("\n[*] Setting up collection: `investors`...")
    investors_col = db["investors"]

    # Create indexes
    idx_result = investors_col.create_indexes(INVESTORS_INDEXES)
    print(f"    [OK] Indexes created: {idx_result}")

    # Seed sample document (upsert so re-running is idempotent)
    result = investors_col.replace_one(
        {"_id": SAMPLE_INVESTOR["_id"]},
        SAMPLE_INVESTOR,
        upsert=True,
    )
    action = "inserted" if result.upserted_id else "updated"
    print(f"    [OK] Sample investor document {action}.")

    # ---- investor_metrics collection -----------------------------------------
    print("\n[*] Setting up collection: `investor_metrics`...")
    metrics_col = db["investor_metrics"]

    # Create indexes
    idx_result = metrics_col.create_indexes(INVESTOR_METRICS_INDEXES)
    print(f"    [OK] Indexes created: {idx_result}")

    # Seed sample document (upsert by investor_id)
    result = metrics_col.replace_one(
        {"investor_id": SAMPLE_INVESTOR_METRICS["investor_id"]},
        SAMPLE_INVESTOR_METRICS,
        upsert=True,
    )
    action = "inserted" if result.upserted_id else "updated"
    print(f"    [OK] Sample investor_metrics document {action}.")

    client.close()
    print("\n[DONE] MongoDB migration completed successfully!")


if __name__ == "__main__":
    run_migration()
