from typing import List, Dict, Any

class CorporateActionAdjuster:
    """
    Utility to adjust historical prices/quantities for corporate actions (splits, bonuses).
    """
    def __init__(self):
        # Mock corporate actions for tests.
        # Format: {symbol: {date: split_factor}}
        self._mock_actions = {
            "TEST_SPLIT": {"2024-01-01": 2.0} # 1:2 split on Jan 1, 2024
        }

    def adjust_deals(self, symbol: str, deals: List[Dict[str, Any]], current_date: str) -> List[Dict[str, Any]]:
        """
        Adjusts historical deals to be directly comparable to the current_date.
        """
        actions = self._mock_actions.get(symbol, {})
        adjusted_deals = []
        for deal in deals:
            adj_deal = deal.copy()
            deal_date = deal["date"]
            
            # Find any splits between deal_date and current_date
            total_factor = 1.0
            for action_date, factor in actions.items():
                if deal_date < action_date <= current_date:
                    total_factor *= factor
            
            if total_factor != 1.0:
                adj_deal["price"] = float(deal.get("price", 0)) / total_factor
                adj_deal["quantity"] = int(deal.get("quantity", 0) * total_factor)
            
            adjusted_deals.append(adj_deal)
            
        return adjusted_deals
