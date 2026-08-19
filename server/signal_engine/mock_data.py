import asyncio
from signal_engine.cache import LookbackCache
from signal_engine.utils import CorporateActionAdjuster
from signal_engine.dal import SignalDAL
from signal_engine.strategy import InstitutionalHerdingStrategy, WhaleConvictionStrategy, RelativeVolumeIntensityStrategy
from signal_engine.orchestrator import SignalEngine
from signal_engine.logger import get_structured_logger

logger = get_structured_logger("signal_engine.mock_data")

async def mock_deal_generator():
    """Generates mock deal data and feeds it to the SignalEngine for testing Phase 2."""
    cache = LookbackCache()
    adjuster = CorporateActionAdjuster()
    dal = SignalDAL(cache=cache, adjuster=adjuster)
    
    engine = SignalEngine(dal=dal, threshold=50.0)
    engine.register_strategy(InstitutionalHerdingStrategy(weight=1.5))
    engine.register_strategy(WhaleConvictionStrategy(weight=2.0))
    engine.register_strategy(RelativeVolumeIntensityStrategy(weight=1.0))

    mock_deals = [
        # Whale Z buying heavily (Herd triggers since X, Y, Z bought recently)
        {"symbol": "RELIANCE", "investor_name": "Whale Z", "txn_type": "BUY", "quantity": 500000, "price": 2500.0, "date": "2023-10-06"},
        # A deal with a symbol that has a 1:2 split mock. 
        # Historical price is 100 on 2023-01. Split happens 2024-01-01.
        # Adjusted historical price = 50. Adjusted Qty = 20k.
        # Current price = 55 (>5% higher). Qty = 15k (>50% of 20k). Should trigger Conviction.
        {"symbol": "TEST_SPLIT", "investor_name": "Whale X", "txn_type": "BUY", "quantity": 15000, "price": 55.0, "date": "2024-02-01"},
    ]

    logger.info("Starting mock deal generation stream...")
    
    for deal in mock_deals:
        logger.info(f"Processing deal: {deal['txn_type']} {deal['symbol']} by {deal['investor_name']}")
        signal = await engine.execute(deal["symbol"], deal)
        
        if signal:
            print("\n" + "="*50)
            print(f"SIGNAL GENERATED: {signal.signal_type.value} {signal.symbol} | Score: {signal.strength_score:.1f}")
            print("Breakdown:")
            for res in signal.strategy_breakdown:
                print(f"  - {res.strategy_name}: {res.score:.1f} ({res.reasoning_metadata})")
            print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(mock_deal_generator())
