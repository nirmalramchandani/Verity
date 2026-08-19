import asyncio
import pandas as pd

from datetime import datetime, timezone
from typing import List, Dict, Any
from .logger import get_structured_logger
from .dal import SignalDAL
from db.mongo import portfolio_holdings_collection, investors_collection

logger = get_structured_logger("signal_engine.exit_engine")

class ExitOrchestrator:
    def __init__(self, dal: SignalDAL):
        self.dal = dal

    async def evaluate_holdings(self, current_date_str: str = None):
        """Runs daily to evaluate active holdings against Exit Rules."""
        logger.info("Starting ExitOrchestrator evaluation...")
        
        if not current_date_str:
            current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")

        active_holdings = list(portfolio_holdings_collection.find({"status": "ACTIVE"}))
        if not active_holdings:
            logger.info("No active holdings found for exit evaluation.")
            return

        for holding in active_holdings:
            await self._evaluate_single_holding(holding, current_date)
            
    async def _evaluate_single_holding(self, holding: dict, current_date: datetime):
        symbol = holding.get("symbol")
        investor_name = holding.get("investor_name")
        entry_date = holding.get("entry_date")
        if isinstance(entry_date, str):
            entry_date = datetime.fromisoformat(entry_date)
            
        days_held = (current_date - entry_date).days
        exit_meta = holding.get("exit_metadata", {})
        
        target_price = exit_meta.get("target_price", 0.0)
        stop_loss = exit_meta.get("stop_loss", 0.0)
        mean_hold_days = holding.get("whale_stats_at_entry", {}).get("mean_holding_duration", 90)

        # Get latest price for symbol (Mocked via DAL or we can assume it's fetched from ingestion)
        # For phase 6 MVP, let's assume we can query recent deals for current price approximation or use a price API
        # We'll use get_symbol_metrics for now
        metrics = await self.dal.get_symbol_metrics(symbol)
        # If we don't have a real time price, use a mock or last known
        current_price = holding.get("entry_price") # Placeholder: Ideally fetch real current price

        # Trigger C: Mirror-Exit (Did this whale sell this symbol recently?)
        # Check recent deals for this whale
        recent_sells = await self.dal.get_whale_symbol_history(investor_name, symbol, limit=5)
        mirror_sell = False
        if not recent_sells.empty:
            sells_after_entry = recent_sells[(recent_sells["txn_type"] == "SELL") & (pd.to_datetime(recent_sells["date"]) >= entry_date)]
            if not sells_after_entry.empty:
                mirror_sell = True

        if mirror_sell:
            await self._trigger_exit(holding, "MIRROR_EXIT", current_price, current_date, "Whale sold the position.")
            return

        # Trigger B: Profit/Loss Target
        if current_price >= target_price:
            await self._trigger_exit(holding, "TARGET_HIT", current_price, current_date, "Target Price Reached.")
            return
        elif current_price <= stop_loss:
            await self._trigger_exit(holding, "STOPPED_OUT", current_price, current_date, "Stop Loss Triggered.")
            return

        # Trigger A: Statistical Time-Exit
        if days_held >= mean_hold_days:
            # We exit if in profit or just time exhausted
            await self._trigger_exit(holding, "TIME_EXHAUSTED", current_price, current_date, "Statistical hold time exceeded.")
            return

    async def _trigger_exit(self, holding: dict, status: str, exit_price: float, exit_date: datetime, reason: str):
        holding_id = holding.get("holding_id")
        if not holding_id:
            # Fallback to _id
            holding_id = holding.get("_id")

        logger.info(f"Triggering Exit for {holding.get('symbol')} by {holding.get('investor_name')}: {status} - {reason}")
        
        portfolio_holdings_collection.update_one(
            {"_id": holding.get("_id")},
            {"$set": {
                "status": status,
                "exit_price": exit_price,
                "exit_date": exit_date,
                "exit_reason": reason
            }}
        )

        # Generate a SELL signal
        signal_dict = {
            "symbol": holding.get("symbol"),
            "signal_type": "SELL",
            "strength_score": 90.0,
            "confidence_label": "HIGH",
            "consensus_level": 3,
            "expert_summary": f"Automated Exit [{status}]: {reason}",
            "timestamp": datetime.now(timezone.utc),
            "strategy_breakdown": []
        }
        await self.dal.save_signal(signal_dict)
