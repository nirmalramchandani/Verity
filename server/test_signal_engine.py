import pytest
import asyncio
from signal_engine.strategy import WhaleConvictionStrategy
from signal_engine.dal import SignalDAL
from signal_engine.cache import LookbackCache
from signal_engine.utils import CorporateActionAdjuster
import pandas as pd

@pytest.mark.asyncio
async def test_whale_conviction_strategy_with_split():
    # Setup
    cache = LookbackCache()
    adjuster = CorporateActionAdjuster()
    dal = SignalDAL(cache, adjuster)
    strategy = WhaleConvictionStrategy()

    # We mock the dal's get_whale_symbol_history specifically for this test
    # History: Buy 10000 @ 100 on 2023-01-01
    # Split: 1:2 on 2024-01-01 (handled by mock actions in adjuster: TEST_SPLIT)
    # Adjusted History should be: Buy 20000 @ 50
    async def mock_history(client_name, symbol, limit):
        return pd.DataFrame([
            {"investor_name": client_name, "symbol": symbol, "txn_type": "BUY", "quantity": 10000, "price": 100.0, "date": "2023-01-01"}
        ])
    dal.get_whale_symbol_history = mock_history

    # Scenario 1: Buys > 5% higher than adjusted price (50 * 1.05 = 52.5) AND qty >= 50% of adjusted qty (10000)
    deal_data_hit = {
        "investor_name": "Whale X", "symbol": "TEST_SPLIT", "txn_type": "BUY", 
        "quantity": 15000, "price": 55.0, "date": "2024-02-01"
    }
    
    result_hit = await strategy.evaluate("TEST_SPLIT", deal_data_hit, dal)
    assert result_hit.score == 85.0
    assert "averaging up" in result_hit.reasoning_metadata.lower()

    # Scenario 2: Price is high enough, but quantity is too low (< 10000)
    deal_data_low_qty = {
        "investor_name": "Whale X", "symbol": "TEST_SPLIT", "txn_type": "BUY", 
        "quantity": 5000, "price": 55.0, "date": "2024-02-01"
    }
    result_low_qty = await strategy.evaluate("TEST_SPLIT", deal_data_low_qty, dal)
    assert result_low_qty.score == 0.0

    # Scenario 3: Quantity is high enough, but price is not > 5% higher than adjusted WAP
    deal_data_low_price = {
        "investor_name": "Whale X", "symbol": "TEST_SPLIT", "txn_type": "BUY", 
        "quantity": 15000, "price": 51.0, "date": "2024-02-01"
    }
    result_low_price = await strategy.evaluate("TEST_SPLIT", deal_data_low_price, dal)
    assert result_low_price.score == 0.0
