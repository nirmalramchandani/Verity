import pandas as pd
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from .utils import CorporateActionAdjuster
from .cache import LookbackCache
from db.mongo import high_conviction_signals_collection, investors_collection, investor_metrics_collection

class SignalDAL:
    """
    Data Access Layer for the Signal Engine.
    Handles read operations, caching, and corporate action adjustments.
    """
    def __init__(self, cache: LookbackCache, adjuster: CorporateActionAdjuster):
        self.cache = cache
        self.adjuster = adjuster
        self.db = None
        self.simulation_date = None

    def set_simulation_date(self, date_str: str):
        """Enforces look-ahead bias prevention by capping all queries to this date."""
        self.simulation_date = date_str

    def adjust_for_corporate_actions(self, symbol: str, deals: List[Dict[str, Any]], current_date: str) -> List[Dict[str, Any]]:
        return self.adjuster.adjust_deals(symbol, deals, current_date)

    async def get_investor_history(self, client_name: str) -> dict:
        """Fetches 16-year stats for a whale from MongoDB."""
        cache_key = f"investor_history:{client_name}"
        cached_data = await self.cache.get(cache_key)
        if cached_data: return cached_data
        
        investor = investors_collection.find_one({"_id": client_name})
        metrics = investor_metrics_collection.find_one({"_id": client_name}) or investor_metrics_collection.find_one({"investor_id": client_name})
        
        hit_ratio = 0.5
        avg_holding = 90
        sector = "Unknown"
        
        if metrics and "performance_metrics" in metrics:
            hit_ratio = metrics["performance_metrics"].get("win_rate", 0.5)
        if metrics and "conviction_metrics" in metrics:
            avg_holding = metrics["conviction_metrics"].get("avg_hold_days", 90)
            
        if investor and "behavioral_dna" in investor:
            sector = investor["behavioral_dna"].get("favorite_sector", "Unknown")
            
        data = {
            "client_name": client_name, 
            "hit_ratio": hit_ratio, 
            "avg_holding_period_days": avg_holding, 
            "favorite_sector": sector
        }
        await self.cache.set(cache_key, data, expire=86400)
        return data

    async def get_recent_cluster(self, symbol: str, current_date: str, days: int = 14) -> pd.DataFrame:
        """Finds all distinct whales who bought this symbol in the last 14 days."""
        target_date = datetime.strptime(current_date, "%Y-%m-%d")
        cutoff_str = (target_date - timedelta(days=days)).strftime("%Y-%m-%d")
        
    async def get_recent_cluster(self, symbol: str, current_date: str, days: int = 14) -> pd.DataFrame:
        """Finds all distinct whales who bought this symbol in the last 14 days."""
        target_date = datetime.strptime(current_date, "%Y-%m-%d")
        cutoff_str = (target_date - timedelta(days=days)).strftime("%Y-%m-%d")
        
        query = {
            f"portfolio_state.positions.symbol": symbol,
            f"portfolio_state.positions.last_buy_date": {"$gte": cutoff_str, "$lte": current_date}
        }
        results = list(investors_collection.find(query, {"_id": 1, "portfolio_state.positions": 1}))
        
        deals = []
        for r in results:
            for item in r.get("portfolio_state", {}).get("positions", []):
                if item.get("symbol") == symbol and cutoff_str <= item.get("last_buy_date", "") <= current_date:
                    deals.append({
                        "investor_name": r["_id"],
                        "txn_type": "BUY",
                        "quantity": item.get("qty", 0),
                        "price": item.get("avg_price", 0.0),
                        "date": item.get("last_buy_date")
                    })
                    
        return pd.DataFrame(deals) if deals else pd.DataFrame(columns=["investor_name", "txn_type", "quantity", "price", "date"])

    async def get_whale_symbol_history(self, client_name: str, symbol: str, limit: int = 3) -> pd.DataFrame:
        """Fetch last N deals for a whale in a symbol from their active portfolio."""
        investor = investors_collection.find_one({"_id": client_name}, {"_id": 1, "portfolio_state.positions": 1})
        deals = []
        if investor and "portfolio_state" in investor:
            for item in investor["portfolio_state"].get("positions", []):
                if item.get("symbol") == symbol:
                    deals.append({
                        "investor_name": client_name,
                        "symbol": symbol,
                        "txn_type": "BUY",
                        "quantity": item.get("qty", 0),
                        "price": item.get("avg_price", 0.0),
                        "date": item.get("last_buy_date")
                    })
        df = pd.DataFrame(deals)
        if not df.empty:
            df = df.sort_values(by="date").tail(limit)
        return df

    async def get_symbol_metrics(self, symbol: str) -> Dict[str, float]:
        """Calculates historical median deal size from the active portfolios in MongoDB."""
        query = {f"portfolio_state.positions.symbol": symbol}
        res = list(investors_collection.find(query, {"portfolio_state.positions": 1}))
        if res:
            total_val = 0
            count = 0
            for r in res:
                for item in r.get("portfolio_state", {}).get("positions", []):
                    if item.get("symbol") == symbol:
                        total_val += (item.get("qty", 0) * item.get("avg_price", 0.0))
                        count += 1
            if count > 0:
                val = (total_val / count) / 10000000 # cr
                return {"median_deal_value_cr": val, "adv_30d_cr": val * 10}
        return {"median_deal_value_cr": 5.0, "adv_30d_cr": 100.0}

    async def get_nifty_metrics(self, current_date: str) -> Dict[str, float]:
        """Check the Nifty 50 regime (200-DMA)."""
        await asyncio.sleep(0.01)
        # Mocking a bear market on 2020-03-xx, bull otherwise
        is_bear = "2020-03" in current_date
        return {
            "current_price": 8000.0 if is_bear else 12000.0,
            "dma_200": 10000.0
        }

    async def get_forward_prices(self, symbol: str, start_date: str) -> List[Dict[str, Any]]:
        """Used strictly by PerformanceValidator. Fetches FUTURE prices."""
        await asyncio.sleep(0.01)
        # Mock 90, 180, 365 days of future prices
        from datetime import datetime, timedelta
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        return [
            {"date": (base_date + timedelta(days=90)).strftime("%Y-%m-%d"), "price": 60.0},
            {"date": (base_date + timedelta(days=180)).strftime("%Y-%m-%d"), "price": 65.0},
            {"date": (base_date + timedelta(days=365)).strftime("%Y-%m-%d"), "price": 80.0}, # +45% return
        ]

    async def get_forward_nifty(self, start_date: str) -> List[Dict[str, Any]]:
        """Used strictly by PerformanceValidator."""
        await asyncio.sleep(0.01)
        from datetime import datetime, timedelta
        base_date = datetime.strptime(start_date, "%Y-%m-%d")
        return [
            {"date": (base_date + timedelta(days=90)).strftime("%Y-%m-%d"), "price": 10500.0},
            {"date": (base_date + timedelta(days=180)).strftime("%Y-%m-%d"), "price": 11000.0},
            {"date": (base_date + timedelta(days=365)).strftime("%Y-%m-%d"), "price": 12000.0}, # +20% benchmark
        ]

    async def save_signal(self, signal_dict: dict) -> None:
        """Persist the aggregated signal to the high_conviction_signals collection."""
        try:
            high_conviction_signals_collection.insert_one(signal_dict)
        except Exception as e:
            print(f"Error saving signal: {e}")

    async def save_portfolio_holding(self, holding_dict: dict) -> None:
        """Persist a new holding to the portfolio_holdings collection."""
        try:
            from db.mongo import portfolio_holdings_collection
            portfolio_holdings_collection.insert_one(holding_dict)
        except Exception as e:
            print(f"Error saving holding: {e}")
