import json
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict, Any

from signal_engine.orchestrator import SignalEngine
from signal_engine.dal import SignalDAL
from signal_engine.cache import LookbackCache
from signal_engine.utils import CorporateActionAdjuster
from signal_engine.strategy import InstitutionalHerdingStrategy, WhaleConvictionStrategy, RelativeVolumeIntensityStrategy
from signal_engine.logger import get_structured_logger

logger = get_structured_logger("signal_engine.backtest")

class GlobalMarketFilter:
    """Checks if the broader market is in a bear regime."""
    def __init__(self, dal: SignalDAL):
        self.dal = dal

    async def is_bear_market(self, simulation_date: str) -> bool:
        """Returns True if Nifty 50 is trading below its 200-DMA."""
        nifty_metrics = await self.dal.get_nifty_metrics(simulation_date)
        return nifty_metrics.get("current_price", 0) < nifty_metrics.get("dma_200", 0)

class PerformanceValidator:
    """Calculates forward-looking performance metrics for generated signals."""
    def __init__(self, dal: SignalDAL):
        self.dal = dal

    async def calculate_metrics(self, symbol: str, entry_price: float, simulation_date: str) -> Dict[str, Any]:
        """Calculates T+90, T+180, T+365 returns, Alpha, and MDD."""
        forward_data = await self.dal.get_forward_prices(symbol, simulation_date)
        nifty_data = await self.dal.get_forward_nifty(simulation_date)
        
        if not forward_data:
            return {"error": "Delisted or Missing Data"}
            
        metrics = {}
        for days in [90, 180, 365]:
            period_data = [d for d in forward_data if (datetime.strptime(d["date"], "%Y-%m-%d") - datetime.strptime(simulation_date, "%Y-%m-%d")).days <= days]
            
            if not period_data:
                continue
                
            future_price = period_data[-1]["price"]
            abs_return = ((future_price - entry_price) / entry_price) * 100
            
            # MDD Calculation
            peak = entry_price
            max_drawdown = 0.0
            for day in period_data:
                if day["price"] > peak:
                    peak = day["price"]
                drawdown = (peak - day["price"]) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # Alpha
            nifty_period = [d for d in nifty_data if (datetime.strptime(d["date"], "%Y-%m-%d") - datetime.strptime(simulation_date, "%Y-%m-%d")).days <= days]
            alpha = 0.0
            if nifty_period:
                nifty_entry = nifty_period[0]["price"]
                nifty_future = nifty_period[-1]["price"]
                nifty_return = ((nifty_future - nifty_entry) / nifty_entry) * 100
                alpha = abs_return - nifty_return
                
            metrics[f"T+{days}"] = {
                "abs_return_pct": abs_return,
                "alpha_pct": alpha,
                "mdd_pct": max_drawdown * 100
            }
            
        return metrics

class BacktestRunner:
    """Orchestrates the Time Machine loop and backtests the Signal Engine."""
    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.results = []
        
    async def run_day(self, current_date: str, deals: List[Dict[str, Any]]) -> List[Dict]:
        """Runs the engine for a single simulated day."""
        dal = SignalDAL(cache=LookbackCache(), adjuster=CorporateActionAdjuster())
        dal.set_simulation_date(current_date) # Enforce strict look-ahead bias prevention
        
        engine = SignalEngine(dal=dal, noise_threshold=60.0)
        engine.register_strategy(InstitutionalHerdingStrategy(weight=0.4))
        engine.register_strategy(WhaleConvictionStrategy(weight=0.4))
        engine.register_strategy(RelativeVolumeIntensityStrategy(weight=0.2))
        
        market_filter = GlobalMarketFilter(dal)
        validator = PerformanceValidator(dal)
        
        is_bear = await market_filter.is_bear_market(current_date)
        day_results = []
        
        for deal in deals:
            signal = await engine.execute(deal["symbol"], deal)
            if signal:
                # Apply Market Regime Safety Filter
                if is_bear:
                    signal.strength_score *= 0.5
                    signal.expert_summary = "[BEAR MARKET PENALTY APPLIED] " + signal.expert_summary
                    if signal.strength_score < 70:
                        signal.confidence_label = "SPECULATIVE"

                if signal.confidence_label in ["HIGH", "CRITICAL"]:
                    # Forward Testing
                    perf = await validator.calculate_metrics(deal["symbol"], deal.get("price", 0), current_date)
                    
                    result_record = {
                        "simulation_date": current_date,
                        "signal": signal.model_dump(mode='json'),
                        "performance": perf,
                        "investor_name": deal.get("investor_name")
                    }
                    day_results.append(result_record)
                    
        return day_results

    def _sync_run_year(self, year: int) -> List[Dict]:
        """Synchronous wrapper for multiprocessing pool."""
        # Mocking daily iteration for a year
        dates = [f"{year}-06-15", f"{year}-11-20"] 
        mock_deals_by_date = {
            dates[0]: [{"symbol": "TEST_SPLIT", "investor_name": "Whale X", "txn_type": "BUY", "quantity": 15000, "price": 55.0, "date": dates[0]}],
            dates[1]: [{"symbol": "HDFCBANK", "investor_name": "Whale Y", "txn_type": "BUY", "quantity": 50000, "price": 1500.0, "date": dates[1]}],
        }
        
        year_results = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for date in dates:
            deals = mock_deals_by_date.get(date, [])
            if deals:
                day_res = loop.run_until_complete(self.run_day(date, deals))
                year_results.extend(day_res)
                
        loop.close()
        return year_results

    def execute_parallel_backtest(self, version_tag: str):
        """Runs the 16-year simulation in parallel using multiprocessing."""
        logger.info(f"Starting parallel backtest from {self.start_date} to {self.end_date}")
        
        start_year = int(self.start_date.split("-")[0])
        end_year = int(self.end_date.split("-")[0])
        years = list(range(start_year, end_year + 1))
        
        all_results = []
        with ProcessPoolExecutor(max_workers=4) as executor:
            for year_res in executor.map(self._sync_run_year, years):
                all_results.extend(year_res)
                
        # Generate Summary Report
        total_signals = len(all_results)
        alphas = []
        for r in all_results:
            t365 = r.get("performance", {}).get("T+365", {})
            if "alpha_pct" in t365: alphas.append(t365["alpha_pct"])
            
        avg_alpha = sum(alphas) / len(alphas) if alphas else 0.0
        
        report = {
            "metadata": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "total_signals": total_signals,
                "average_alpha_1yr": avg_alpha,
            },
            "signals": all_results
        }
        
        # Save JSON
        filename = f"backtest_v{version_tag}_results.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Backtest completed. Generated {total_signals} signals. Average 1-Year Alpha: {avg_alpha:.2f}%. Saved to {filename}")
        return report

if __name__ == "__main__":
    runner = BacktestRunner("2010-01-01", "2026-05-01")
    runner.execute_parallel_backtest("1.0_weights_0.4_0.4_0.2")
