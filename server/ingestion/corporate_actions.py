"""
Pure functions for applying corporate actions to an investor's open lots.

Supported actions:
- BONUS
- SPLIT / REVERSE_SPLIT
- MERGER / DEMERGER (temporary liquidation logic)
"""
import re

def parse_ratio(purpose_str: str):
    """
    Extract a ratio like "1:1" or "2:5" from a purpose string.
    Returns (numerator, denominator) or None if not found.
    Fallback to returning None so the caller can skip or log a warning.
    """
    match = re.search(r'(\d+)\s*:\s*(\d+)', purpose_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def apply_bonus(lots: list, ratio_num: int, ratio_den: int):
    """
    Apply a bonus action to a list of open lots.
    A 1:1 bonus means for every 1 share held, you get 1 free.
    New qty = old_qty + (old_qty * num / den).
    Price adjusts down proportionally to maintain cost basis.
    """
    if ratio_den == 0:
        return

    bonus_factor = ratio_num / ratio_den
    
    for lot in lots:
        original_qty = lot["qty"]
        bonus_qty = int(original_qty * bonus_factor)
        
        # Adjust qty up, price down
        new_qty = original_qty + bonus_qty
        
        if new_qty > 0:
            lot["price"] = (lot["price"] * original_qty) / new_qty
            lot["qty"] = new_qty


def apply_split(lots: list, ratio_num: int, ratio_den: int):
    """
    Apply a stock split to a list of open lots.
    A 10:2 split (face value 10 to 2) means 5 new shares for 1 old share.
    New qty = old_qty * (num / den).
    Price adjusts down proportionally.
    """
    if ratio_den == 0:
        return
        
    split_factor = ratio_num / ratio_den
    
    for lot in lots:
        original_qty = lot["qty"]
        new_qty = int(original_qty * split_factor)
        
        if new_qty > 0:
            lot["price"] = (lot["price"] * original_qty) / new_qty
            lot["qty"] = new_qty

# NOTE: TEMPORARY LOGIC - We will cure this in the future when a premium corporate action API is integrated.
# Currently, since we cannot automatically determine the exact new ticker symbols and spin-off ratios 
# for 15+ year old data, we simply return a flag to liquidate the parent holding. This prevents the 
# post-demerger price drop from severely corrupting the investor's cost-basis math.
def process_corporate_actions(lots: list, events: list):
    """
    Iterate over the events and apply the corresponding adjustment to the lots in-place.
    Returns (lots, requires_liquidation_flag)
    """
    requires_liquidation = False
    
    for event in events:
        purpose = event["purpose"].upper()
        
        # Attempt to parse ratio
        ratio = parse_ratio(purpose)
        
        if "BONUS" in purpose and ratio:
            apply_bonus(lots, ratio[0], ratio[1])
        elif "SPLIT" in purpose and ratio:
            apply_split(lots, ratio[0], ratio[1])
        elif "DEMERGER" in purpose or "MERGER" in purpose or "AMALGAMATION" in purpose:
            requires_liquidation = True
            lots.clear()
        
    return lots, requires_liquidation
