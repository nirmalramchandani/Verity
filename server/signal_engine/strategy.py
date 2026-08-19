import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any
from .models import StrategyResult

class BaseStrategy(ABC):
    def __init__(self, weight: float = 1.0):
        self.weight = weight

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def evaluate(self, symbol: str, deal_data: Dict[str, Any], dal: Any) -> StrategyResult:
        pass

class InstitutionalHerdingStrategy(BaseStrategy):
    """Detects clustering of independent institutions, weighted by their historical success (hit ratio)."""
    async def evaluate(self, symbol: str, deal_data: Dict[str, Any], dal: Any) -> StrategyResult:
        current_investor = deal_data.get("investor_name", "")
        current_date = deal_data.get("date", "")
        
        cluster_df = await dal.get_recent_cluster(symbol, current_date, days=14)
        
        if cluster_df.empty:
            return StrategyResult(strategy_name=self.name, score=0.0, weight=self.weight, reasoning_metadata="No recent cluster data.", insufficient_data=True)
            
        # Filter for buys and exclude current investor
        buys_df = cluster_df[(cluster_df["txn_type"] == "BUY") & (cluster_df["investor_name"] != current_investor)]
        unique_whales = buys_df["investor_name"].unique()
        
        if len(unique_whales) == 0:
            return StrategyResult(strategy_name=self.name, score=0.0, weight=self.weight, reasoning_metadata="No other Whales in cluster.")

        # Fetch historical hit ratios for each whale in the cluster
        smart_money_score = 0.0
        good_whales = []
        
        for whale in unique_whales:
            dna = await dal.get_investor_history(whale)
            hit_ratio = dna.get("hit_ratio", 0.5)
            # Penalize bad whales, reward good whales
            if hit_ratio > 0.65:
                smart_money_score += 40.0 # Legendary whale
                good_whales.append(whale)
            elif hit_ratio >= 0.50:
                smart_money_score += 20.0 # Decent whale
                good_whales.append(whale)
            else:
                smart_money_score -= 10.0 # Terrible whale (noise)

        # Cap the score
        final_score = max(0.0, min(100.0, smart_money_score))
        
        names = ", ".join(good_whales) if good_whales else "No highly profitable whales"
        reasoning = f"Cluster Score {final_score:.1f}: {len(unique_whales)} Whales detected. Top performing Whales: {names}."
        
        return StrategyResult(strategy_name=self.name, score=final_score, weight=self.weight, reasoning_metadata=reasoning)

class WhaleConvictionStrategy(BaseStrategy):
    """Measures 'Averaging Up' by a whale in a specific stock."""
    async def evaluate(self, symbol: str, deal_data: Dict[str, Any], dal: Any) -> StrategyResult:
        client_name = deal_data.get("investor_name", "")
        current_price = float(deal_data.get("price", 0))
        current_qty = int(deal_data.get("quantity", 0))
        current_date = deal_data.get("date", "")
        txn_type = deal_data.get("txn_type", "")
        
        if txn_type != "BUY":
            return StrategyResult(strategy_name=self.name, score=0.0, weight=self.weight, reasoning_metadata="Deal is not a BUY.")

        history_df = await dal.get_whale_symbol_history(client_name, symbol, limit=3)
        if history_df.empty:
            return StrategyResult(strategy_name=self.name, score=0.0, weight=self.weight, reasoning_metadata="Insufficient Historical Context.", insufficient_data=True)
            
        # Adjust for corporate actions
        history_dicts = history_df.to_dict("records")
        adjusted_history = dal.adjust_for_corporate_actions(symbol, history_dicts, current_date)
        adj_df = pd.DataFrame(adjusted_history)
        
        # Calculate existing position and weighted average price
        buys = adj_df[adj_df["txn_type"] == "BUY"]
        if buys.empty:
            return StrategyResult(strategy_name=self.name, score=0.0, weight=self.weight, reasoning_metadata="No previous buys found in history.")
            
        total_qty = buys["quantity"].sum()
        weighted_avg_price = (buys["quantity"] * buys["price"]).sum() / total_qty
        
        # Criteria
        price_condition = current_price > (weighted_avg_price * 1.05)
        qty_condition = current_qty >= (total_qty * 0.5)
        
        if price_condition and qty_condition:
            score = 85.0
            reasoning = f"Whale averaging up. Current price {current_price:.2f} is >5% higher than WAP {weighted_avg_price:.2f} and Qty {current_qty} is >= 50% of existing {total_qty}."
        else:
            score = 0.0
            reasoning = f"Conditions not met. WAP: {weighted_avg_price:.2f}, Existing Qty: {total_qty}."
            
        return StrategyResult(strategy_name=self.name, score=score, weight=self.weight, reasoning_metadata=reasoning)

class RelativeVolumeIntensityStrategy(BaseStrategy):
    """Distinguishes between Routine Trading and Massive Entry."""
    async def evaluate(self, symbol: str, deal_data: Dict[str, Any], dal: Any) -> StrategyResult:
        metrics = await dal.get_symbol_metrics(symbol)
        median_deal_value_cr = metrics.get("median_deal_value_cr", 0.0)
        adv_30d_cr = metrics.get("adv_30d_cr", 0.0)
        
        current_qty = int(deal_data.get("quantity", 0))
        current_price = float(deal_data.get("price", 0))
        current_value_cr = (current_qty * current_price) / 10_000_000 # Convert to Crores
        
        score = 0.0
        reasoning_parts = []
        
        if median_deal_value_cr > 0 and current_value_cr > (5 * median_deal_value_cr):
            score += 70.0
            reasoning_parts.append(f"Deal value ({current_value_cr:.2f} Cr) is > 5x median ({median_deal_value_cr:.2f} Cr).")
            
        if adv_30d_cr > 0 and current_value_cr > (0.10 * adv_30d_cr):
            score += 20.0
            reasoning_parts.append(f"Deal value is > 10% of 30-day ADV ({adv_30d_cr:.2f} Cr).")
            
        score = min(score, 100.0)
        reasoning = " ".join(reasoning_parts) if reasoning_parts else "Routine volume intensity."
        
        return StrategyResult(strategy_name=self.name, score=score, weight=self.weight, reasoning_metadata=reasoning)

class WhaleExitStrategy(BaseStrategy):
    """Detects when Whales are dumping a stock, signaling a potential EXIT."""
    async def evaluate(self, symbol: str, deal_data: Dict[str, Any], dal: Any) -> StrategyResult:
        txn_type = deal_data.get("txn_type", "")
        if txn_type != "SELL":
            return StrategyResult(strategy_name=self.name, score=0.0, weight=self.weight, reasoning_metadata="Not a SELL deal.")
            
        investor_name = deal_data.get("investor_name", "")
        qty_sold = int(deal_data.get("quantity", 0))
        
        # Check if this is a major liquidation
        dna = await dal.get_investor_history(investor_name)
        hit_ratio = dna.get("hit_ratio", 0.5)
        
        # If a smart whale (hit_ratio > 60%) is selling, it's high conviction
        if hit_ratio > 0.60:
            score = 85.0
            reasoning = f"CRITICAL SELL: Profitable Whale ({investor_name}, {hit_ratio*100:.0f}% HR) is liquidating {qty_sold:,} shares."
        else:
            score = 40.0
            reasoning = f"SELL: Whale {investor_name} is exiting position. Lower conviction (HR: {hit_ratio*100:.0f}%)."
            
        return StrategyResult(strategy_name=self.name, score=score, weight=self.weight, reasoning_metadata=reasoning)
