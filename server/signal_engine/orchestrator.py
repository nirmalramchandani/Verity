import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .models import SignalSchema, StrategyResult, SignalType, WeightingConfig, PortfolioHolding, ExitMetadata
from .strategy import BaseStrategy
from .dal import SignalDAL
from .logger import get_structured_logger

logger = get_structured_logger("signal_engine.orchestrator")

class SignalEngine:
    """
    Orchestrates the execution of multiple strategies, calculates weighted consensus,
    and applies a consensus filter.
    """
    def __init__(self, dal: SignalDAL, weighting_config: WeightingConfig = None, noise_threshold: float = 60.0):
        self.dal = dal
        self.config = weighting_config or WeightingConfig()
        self.config.validate_weights()
        self.noise_threshold = noise_threshold
        self.strategies: List[BaseStrategy] = []

    def register_strategy(self, strategy: BaseStrategy):
        # Override the strategy weight with the config if it exists
        config_weight = getattr(self.config, strategy.name, None)
        if config_weight is not None:
            strategy.weight = config_weight
            
        self.strategies.append(strategy)
        logger.info(f"Registered strategy: {strategy.name} with weight {strategy.weight}")

    async def execute(self, symbol: str, deal_data: Dict[str, Any]) -> Optional[SignalSchema]:
        if not self.strategies:
            logger.warning("No strategies registered in SignalEngine.")
            return None

        # Execute all strategies concurrently
        tasks = [
            strategy.evaluate(symbol, deal_data, self.dal)
            for strategy in self.strategies
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results: List[StrategyResult] = []
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Strategy evaluation failed", extra={"extra_info": {"error": str(res)}})
            else:
                valid_results.append(res)

        if not valid_results:
            return None

        # Handle weight re-normalization if insufficient data
        active_results = []
        insufficient_weight = 0.0
        for res in valid_results:
            if res.insufficient_data:
                insufficient_weight += res.weight
            else:
                active_results.append(res)

        if not active_results:
            return None

        # Renormalize active weights
        total_active_weight_original = sum(res.weight for res in active_results)
        if total_active_weight_original > 0 and insufficient_weight > 0:
            factor = 1.0 / total_active_weight_original
            for res in active_results:
                res.weight = res.weight * factor

        # Calculate weighted consensus score
        consensus_score = sum(res.score * res.weight for res in active_results)

        # Consensus Engine
        triggered_count = sum(1 for res in active_results if res.score >= self.noise_threshold)
        
        # Determine confidence label
        if triggered_count < 2:
            confidence_label = "SPECULATIVE"
        elif consensus_score >= 80:
            confidence_label = "CRITICAL"
        elif consensus_score >= 70:
            confidence_label = "HIGH"
        else:
            confidence_label = "MODERATE"

        # Semantic Aggregation
        txn_type = deal_data.get("txn_type", "BUY")
        signal_type = SignalType.BUY if txn_type == "BUY" else SignalType.SELL
        
        reasoning_list = [res.reasoning_metadata for res in active_results if res.score > 0]
        summary = f"{confidence_label} {signal_type.value} Signal for {symbol}. Reason: " + " ".join(reasoning_list)

        signal = SignalSchema(
            symbol=symbol,
            signal_type=signal_type,
            strength_score=consensus_score,
            confidence_label=confidence_label,
            consensus_level=triggered_count,
            expert_summary=summary,
            strategy_breakdown=valid_results,
            deal_date=deal_data.get("date", "")
        )

        logger.info(f"Signal generated for {symbol}", extra={"extra_info": {"score": consensus_score, "level": triggered_count, "label": confidence_label}})
        
        # Persist to DB
        await self.dal.save_signal(signal.model_dump(mode='json'))
        
        # Phase 6: Exit Engine & Lifecycle - Attach Exit Metadata and create PortfolioHolding
        if signal_type == SignalType.BUY:
            investor_name = deal_data.get("investor_name", "Unknown")
            entry_price = float(deal_data.get("price", 0.0))
            entry_date_str = deal_data.get("date", datetime.now().strftime("%Y-%m-%d"))
            entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d")

            # Fetch Whale stats
            whale_stats = await self.dal.get_investor_history(investor_name)
            avg_return = whale_stats.get("historical_avg_return", 0.15) # default 15%
            max_drawdown = whale_stats.get("max_drawdown", 0.10) # default 10%
            mean_hold_days = whale_stats.get("mean_holding_duration", 90) # default 90 days

            # Calculate triggers
            target_price = entry_price * (1 + avg_return)
            stop_loss = entry_price * (1 - max_drawdown)
            est_exit_date = entry_date + timedelta(days=int(mean_hold_days))

            exit_metadata = ExitMetadata(
                target_price=target_price,
                stop_loss=stop_loss,
                estimated_exit_date=est_exit_date
            )

            holding = PortfolioHolding(
                symbol=symbol,
                investor_name=investor_name,
                entry_price=entry_price,
                entry_date=entry_date,
                whale_stats_at_entry=whale_stats,
                exit_metadata=exit_metadata,
                status="ACTIVE"
            )

            # Persist holding to db
            await self.dal.save_portfolio_holding(holding.model_dump(mode='json'))
            logger.info(f"PortfolioHolding created for {symbol} by {investor_name} with Target: {target_price:.2f}, SL: {stop_loss:.2f}")

        return signal
