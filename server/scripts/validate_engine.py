import pandas as pd
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.processor import IngestProcessor

def test_engine_math():
    print("[*] Running Mathematical Engine Validation...")
    
    # Synthetic Transactions
    # 2024-01-01: Buy 100 @ 100
    # 2024-01-10: Buy 200 @ 120
    # 2024-01-15: Sell 150 @ 150  -> Matches 100 from Lot 1, 50 from Lot 2
    # 2024-01-20: Bonus 1:1 Event (Lot 2 now has 150 shares left, should double to 300, price halves to 60)
    # 2024-01-25: Sell 300 @ 100  -> Matches all 300 from modified Lot 2
    
    txn_data = [
        {"investor_name": "TEST_INV", "stock_symbol": "TEST", "date": pd.to_datetime("2024-01-01").date(), "transaction_type": "BUY", "quantity": 100, "price": 100.0},
        {"investor_name": "TEST_INV", "stock_symbol": "TEST", "date": pd.to_datetime("2024-01-10").date(), "transaction_type": "BUY", "quantity": 200, "price": 120.0},
        {"investor_name": "TEST_INV", "stock_symbol": "TEST", "date": pd.to_datetime("2024-01-15").date(), "transaction_type": "SELL", "quantity": 150, "price": 150.0},
        {"investor_name": "TEST_INV", "stock_symbol": "TEST", "date": pd.to_datetime("2024-01-25").date(), "transaction_type": "SELL", "quantity": 300, "price": 100.0},
    ]
    txn_df = pd.DataFrame(txn_data)
    
    # Synthetic Events
    event_data = [
        {"stock_symbol": "TEST", "company_name": "TEST CO", "series": "EQ", "purpose": "BONUS 1:1", "ex_date": pd.to_datetime("2024-01-20").date(), "record_date": None}
    ]
    events_df = pd.DataFrame(event_data)
    
    # Override Postgres write for the test but capture the sell_rec
    captured_sells = []
    
    class TestProcessor(IngestProcessor):
        def _sync_persist_row(self, row_idx, investor_id, txn_date, state, sell_rec):
            if sell_rec:
                captured_sells.append(sell_rec)
        
        def _sync_persist_monthly_snapshots(self, target_date):
            yield "[INFO] mock snapshots"
            
    proc = TestProcessor(txn_df, events_df)
    
    # run() is now a generator, consume it fully
    for _ in proc.run(): pass
    
    # --- Assertions ---
    sells = captured_sells
    
    # Sell 1: 150 shares @ 150
    # 100 from lot 1 @ 100 -> PnL: 100 * 50 = 5000
    # 50 from lot 2 @ 120 -> PnL: 50 * 30 = 1500
    # Total PnL = 6500. Total Cost = 10000 + 6000 = 16000. Pct = (6500/16000) * 100 = 40.625%
    
    sell_1 = sells[0]
    assert sell_1[3] == 150, f"Expected 150 qty, got {sell_1[3]}"
    assert sell_1[5] == 6500.0, f"Expected 6500 PnL, got {sell_1[5]}"
    
    # Sell 2: 300 shares @ 100
    # Lot 2 had 150 shares @ 120 left.
    # Bonus 1:1 applied on Jan 20. Lot 2 becomes 300 shares @ 60.
    # Sell 300 @ 100 -> PnL: 300 * (100 - 60) = 12000.
    sell_2 = sells[1]
    assert sell_2[3] == 300, f"Expected 300 qty, got {sell_2[3]}"
    assert sell_2[5] == 12000.0, f"Expected 12000 PnL, got {sell_2[5]}"
    
    # Verify open positions is exactly 0
    state = proc.investor_states["TEST_INV"]
    # We must find the position for "TEST"
    test_pos = None
    for p in state["portfolio_state"]["positions"]:
        if p["symbol"] == "TEST":
            test_pos = p
            break
            
    assert test_pos and test_pos["qty"] == 0, f"Expected 0 qty, got {test_pos}"
    
    print("[OK] All Mathematical and Corporate Action Proofs Passed!")

if __name__ == "__main__":
    test_engine_math()
