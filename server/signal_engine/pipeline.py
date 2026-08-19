import asyncio
import argparse
from datetime import datetime

from signal_engine.orchestrator import SignalEngine
from signal_engine.dal import SignalDAL
from signal_engine.cache import LookbackCache
from signal_engine.utils import CorporateActionAdjuster
from signal_engine.enrichment import ContextualistAgent
from signal_engine.alerting import NotificationService
from signal_engine.logger import get_structured_logger
from signal_engine.strategy import InstitutionalHerdingStrategy, WhaleConvictionStrategy, RelativeVolumeIntensityStrategy, WhaleExitStrategy
from signal_engine.exit_engine import ExitOrchestrator
from db.mongo import high_conviction_signals_collection, investors_collection

logger = get_structured_logger("signal_engine.pipeline")

class EndToEndPipeline:
    def __init__(self):
        self.cache = LookbackCache()
        self.adjuster = CorporateActionAdjuster()
        self.dal = SignalDAL(self.cache, self.adjuster)
        self.engine = SignalEngine(self.dal)
        
        # Register the strategies
        self.engine.register_strategy(InstitutionalHerdingStrategy())
        self.engine.register_strategy(WhaleConvictionStrategy())
        self.engine.register_strategy(RelativeVolumeIntensityStrategy())
        self.engine.register_strategy(WhaleExitStrategy())
        
        self.ai_agent = ContextualistAgent()
        self.alerter = NotificationService()

    async def run_daily_batch(self):
        # Fetch real recent deals from MongoDB to test the pipeline
        investors = list(investors_collection.find({"portfolio_state": {"$exists": True}}))
        
        all_deals = []
        for inv in investors:
            for item in inv.get("portfolio_state", {}).get("positions", []):
                if item.get("last_buy_date"):
                    all_deals.append({
                        "symbol": item["symbol"],
                        "investor_name": inv["_id"],
                        "quantity": item.get("qty", 0),
                        "price": item.get("avg_price", 0.0),
                        "date": item["last_buy_date"]
                    })
                    
        # Sort by buy_date descending and pick the 50 most recent unique deals
        all_deals.sort(key=lambda x: x["date"], reverse=True)
        recent_deals_raw = all_deals[:50]
        
        if not recent_deals_raw:
            logger.error("No real data found in MongoDB to run the pipeline on.")
            return

        # Ensure we only process unique symbols
        symbols_processed = set()
        daily_deals = []
        for deal in recent_deals_raw:
            if deal["symbol"] not in symbols_processed:
                daily_deals.append(deal)
                symbols_processed.add(deal["symbol"])
                
        logger.info(f"Starting daily pipeline execution for {len(daily_deals)} deals. Symbols: {[d['symbol'] for d in daily_deals]}")

        signals = []
        for deal in daily_deals:
            # Set the simulation date to the deal's date so we don't look ahead
            self.dal.set_simulation_date(deal["date"])
            signal = await self.engine.execute(deal["symbol"], deal)
            if signal and signal.strength_score >= 70:
                signals.append((signal, deal["investor_name"]))

        logger.info(f"Engine generated {len(signals)} High-Conviction signals.")

        # Phase 5: RAG Enrichment & Alerting
        for signal, client_name in signals:
            dna = await self.dal.get_investor_history(client_name)
            enriched_signal = await self.ai_agent.enrich_signal(signal, dna)
            
            # Update the database with the enriched summary
            high_conviction_signals_collection.update_one(
                {"signal_id": str(signal.signal_id)},
                {"$set": {"expert_summary": enriched_signal.expert_summary}}
            )
            
            # 6:30 PM: Email Alert
            await self.alerter.send_alert(enriched_signal)

        # Phase 6: Exit Engine execution
        logger.info("Starting Phase 6: Exit Engine evaluation...")
        exit_orchestrator = ExitOrchestrator(self.dal)
        await exit_orchestrator.evaluate_holdings()
            
        logger.info("Daily pipeline execution completed.")

async def main():
    pipeline = EndToEndPipeline()
    await pipeline.run_daily_batch()

if __name__ == "__main__":
    asyncio.run(main())
