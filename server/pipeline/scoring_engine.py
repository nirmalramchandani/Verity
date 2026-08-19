"""
pipeline/scoring_engine.py
==========================
Calculates AI ranking scores (Smart Money, Conviction, Consistency, Risk Management)
based on previously calculated investor metrics, and updates MongoDB and PostgreSQL.
"""
from datetime import datetime
from db.mongo import investors_collection, investor_metrics_collection
from db.postgres import get_connection

def calculate_scores():
    print("[scoring] Starting AI scoring calculation for all investors...")
    
    # We will update these scores back to investors_collection and investor_snapshots
    # investor_snapshots requires a date. Since we run this after ingestion, we'll
    # query the latest snapshot for each investor or update them all. It's best to 
    # just update the newest snapshot, or simply update where investor_id matches.
    # To be safe, we'll just update ALL snapshots for that investor, or only the latest.
    
    metrics_cursor = investor_metrics_collection.find({})
    investors_cursor = investors_collection.find({})
    
    # Build maps for fast parallel lookup
    investor_metrics = {doc["investor_id"]: doc for doc in metrics_cursor}
    investors = {doc["_id"]: doc for doc in investors_cursor}
    
    updates_mongo = []
    updates_pg = []
    
    for inv_id, metrics in investor_metrics.items():
        inv_doc = investors.get(inv_id)
        if not inv_doc:
            continue
            
        pm = metrics.get("performance_metrics", {})
        cm = metrics.get("conviction_metrics", {})
        csm = metrics.get("consistency_metrics", {})
        dna = inv_doc.get("behavioral_dna", {})
        identity = inv_doc.get("identity", {})
        
        # Extract variables
        total_trades = pm.get("total_trades", 0)
        win_rate = pm.get("win_rate", 0.0)
        profit_factor = pm.get("profit_factor", 0.0)
        longest_win_streak = csm.get("longest_win_streak", 0)
        
        max_drawdown_pct = pm.get("max_drawdown_pct", 0.0)
        avg_profit_pct = pm.get("avg_profit_pct", 0.0)
        avg_loss_pct = pm.get("avg_loss_pct", 0.0)
        
        avg_hold_days = cm.get("avg_hold_days", 0.0)
        avg_position_size_pct = cm.get("avg_position_size_pct", 0.0)
        
        entry_style = dna.get("entry_style", "UNKNOWN")
        exit_style = dna.get("exit_style", "UNKNOWN")
        investor_type = identity.get("investor_type", "UNKNOWN")

        # ---------------------------------------------------------
        # 1. Consistency Score (0-100)
        # ---------------------------------------------------------
        w_win_rate = win_rate * 50.0
        w_pf = min(profit_factor, 3.0) / 3.0 * 30.0
        w_streak = min(longest_win_streak, 10) / 10.0 * 20.0
        consistency_score = w_win_rate + w_pf + w_streak
        
        # ---------------------------------------------------------
        # 2. Risk Management Score (0-100)
        # ---------------------------------------------------------
        w_drawdown = max(0.0, 50.0 - max_drawdown_pct)
        if avg_loss_pct == 0:
            reward_risk = 3.0 if avg_profit_pct > 0 else 0.0
        else:
            reward_risk = abs(avg_profit_pct / avg_loss_pct)
        w_rr = min(reward_risk, 3.0) / 3.0 * 30.0
        w_exit = 20.0 if exit_style == "GRADUAL" else 10.0
        risk_mgt_score = w_drawdown + w_rr + w_exit
        
        # ---------------------------------------------------------
        # 3. Conviction Score (0-100)
        # ---------------------------------------------------------
        w_hold = min(avg_hold_days, 180.0) / 180.0 * 50.0
        w_size = min(avg_position_size_pct * 100.0, 30.0)
        w_entry = 20.0 if entry_style == "STAGGERED" else 10.0
        conviction_score = w_hold + w_size + w_entry
        
        # ---------------------------------------------------------
        # 4. Smart Money Score (0-100)
        # ---------------------------------------------------------
        scale_bonus = 0.0
        if investor_type in ["OPERATOR", "LARGE_INVESTOR"]:
            scale_bonus = 20.0
        elif investor_type == "MID_INVESTOR":
            scale_bonus = 10.0
            
        smart_money_score = (consistency_score * 0.35) + (risk_mgt_score * 0.35) + (conviction_score * 0.1) + scale_bonus
        
        # Low Volume dampener: If less than 3 trades completed
        if total_trades < 3:
            consistency_score = min(consistency_score, 50.0)
            risk_mgt_score = min(risk_mgt_score, 50.0)
            conviction_score = min(conviction_score, 50.0)
            smart_money_score = min(smart_money_score, 50.0)
            
        # Ensure hard ceiling of 99.9
        consistency_score = round(min(consistency_score, 99.9), 2)
        risk_mgt_score = round(min(risk_mgt_score, 99.9), 2)
        conviction_score = round(min(conviction_score, 99.9), 2)
        smart_money_score = round(min(smart_money_score, 99.9), 2)

        # Build update operations
        updates_mongo.append({
            "filter": {"_id": inv_id},
            "update": {
                "$set": {
                    "ranking_scores.smart_money_score": smart_money_score,
                    "ranking_scores.consistency_score": consistency_score,
                    "ranking_scores.conviction_score": conviction_score,
                    "ranking_scores.risk_management_score": risk_mgt_score
                }
            }
        })
        
        updates_pg.append((
            smart_money_score, consistency_score, conviction_score, risk_mgt_score, inv_id
        ))

    # Commit to MongoDB
    for op in updates_mongo:
        investors_collection.update_one(op["filter"], op["update"])
        
    # Commit to Postgres (REMOVED: To prevent overwriting historical snapshots)
    # We no longer update investor_snapshots here because it flattens the historical monthly progression.

    print(f"[scoring] Completed. {len(updates_mongo)} investors scored and persisted.")

if __name__ == "__main__":
    calculate_scores()
