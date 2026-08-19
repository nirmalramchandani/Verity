import asyncio
from signal_engine.orchestrator import SignalEngine
from signal_engine.dal import SignalDAL
from signal_engine.cache import LookbackCache
from signal_engine.utils import CorporateActionAdjuster
from signal_engine.strategy import BaseStrategy
from signal_engine.models import StrategyResult

# Mock Strategies for Phase 3 testing
class MockStrategyA(BaseStrategy):
    async def evaluate(self, symbol, deal_data, dal):
        return StrategyResult(strategy_name="InstitutionalHerdingStrategy", score=90.0, weight=self.weight, reasoning_metadata="Herd of 4 Whales.")

class MockStrategyB(BaseStrategy):
    async def evaluate(self, symbol, deal_data, dal):
        return StrategyResult(strategy_name="WhaleConvictionStrategy", score=85.0, weight=self.weight, reasoning_metadata="Conviction 'Average-Up' move by Whale X.")

class MockStrategyC(BaseStrategy):
    async def evaluate(self, symbol, deal_data, dal):
        return StrategyResult(strategy_name="RelativeVolumeIntensityStrategy", score=20.0, weight=self.weight, reasoning_metadata="Volume intensity is weak.")

async def test_phase3_consensus():
    dal = SignalDAL(cache=LookbackCache(), adjuster=CorporateActionAdjuster())
    engine = SignalEngine(dal=dal) # Uses default WeightingConfig (0.4, 0.4, 0.2)
    
    # Register our mock strategies with names matching the config
    a = MockStrategyA()
    a.__class__.__name__ = "InstitutionalHerdingStrategy"
    b = MockStrategyB()
    b.__class__.__name__ = "WhaleConvictionStrategy"
    c = MockStrategyC()
    c.__class__.__name__ = "RelativeVolumeIntensityStrategy"
    
    engine.register_strategy(a)
    engine.register_strategy(b)
    engine.register_strategy(c)

    deal = {"txn_type": "BUY"}
    signal = await engine.execute("TEST_SYMBOL", deal)

    print("\n" + "="*60)
    print("PHASE 3 CONSENSUS ENGINE TEST")
    print("="*60)
    print(f"Confidence Label: {signal.confidence_label}")
    print(f"Consensus Score:  {signal.strength_score:.1f}")
    print(f"Consensus Level:  {signal.consensus_level}")
    print(f"Expert Summary:\n{signal.expert_summary}")
    print("="*60 + "\n")
    
    assert signal.confidence_label == "HIGH"
    assert signal.consensus_level == 2
    # 90*0.4 + 85*0.4 + 20*0.2 = 36 + 34 + 4 = 74
    assert signal.strength_score == 74.0

if __name__ == "__main__":
    asyncio.run(test_phase3_consensus())
