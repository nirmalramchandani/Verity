"""
ingestion/processor.py
======================
Row-by-row synchronous ingestion engine.

Every transaction is processed in strict chronological order (BUY before SELL
on same date). After every single row the following are re-evaluated and
persisted immediately to both databases:

  MongoDB  investors         → live portfolio + ranking + behavioral_dna
  MongoDB  investor_metrics  → exhaustive analytics (win-rate, pnl, etc.)
  Postgres sell_transactions → per-sell record with FIFO PnL
  Postgres ingestion_status  → resume checkpoint

Investor Classification (evaluated on EVERY transaction):
  - OPERATOR      : avg trade value > 200 000 AND penny-stock ratio > 40 %
  - LARGE_INVESTOR: avg trade value >= 500 000 (regardless of penny ratio)
  - SMALL_INVESTOR: avg trade value < 100 000
  - MID_INVESTOR  : 100 000 to 500 000 (covers most retail HNI / small MF)
  - MIXED         : pattern that doesn't fit cleanly into any one bucket

Penny stock threshold  : price < 50
Large trade threshold  : trade value (qty * price) > 200 000
"""

import math
import json
import os
import calendar
from datetime import datetime, date
from decimal import Decimal, getcontext

import pandas as pd

from db.postgres import get_connection
from db.mongo import investors_collection, investor_metrics_collection
from ingestion.corporate_actions import process_corporate_actions


# ---------------------------------------------------------------------------
# Constants / Thresholds
# ---------------------------------------------------------------------------
PENNY_PRICE_THRESHOLD   = 50          # stocks priced below this are "penny"
LARGE_TRADE_VALUE       = 200_000     # single trade value (qty * price) to be "large"
OPERATOR_PENNY_RATIO    = 0.40        # ≥40 % of trades in penny stocks + heavy → OPERATOR
LARGE_INVESTOR_AVG      = 500_000     # avg trade value to be LARGE_INVESTOR
SMALL_INVESTOR_AVG      = 100_000     # avg trade value below this → SMALL_INVESTOR

# Market-cap classification by share price (Indian market proxy)
LARGECAP_PRICE_THRESHOLD = 1000       # price >= 1000 → LARGE_CAP
MIDCAP_PRICE_THRESHOLD   = 200        # 200 <= price < 1000 → MID_CAP
                                      # price < 200 → SMALL_CAP

# ---------------------------------------------------------------------------
# Module-level data: sector mapping + investor aliases (loaded once)
# ---------------------------------------------------------------------------
_PIPELINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline")

def _load_json(filename: str) -> dict:
    path = os.path.join(_PIPELINE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

SECTOR_MAP     = _load_json("sector_mapping.json")      # symbol → sector
INVESTOR_ALIAS = _load_json("investor_aliases.json")     # alias → canonical


def _classify_mcap(price: float) -> str:
    """Classify market-cap bucket by share price as proxy."""
    if price >= LARGECAP_PRICE_THRESHOLD:
        return "LARGE_CAP"
    if price >= MIDCAP_PRICE_THRESHOLD:
        return "MID_CAP"
    return "SMALL_CAP"


def _get_sector(symbol: str) -> str:
    """Lookup sector for a symbol from the static mapping."""
    return SECTOR_MAP.get(symbol, "OTHER")


def _get_aliases(investor_name: str) -> list:
    """Return list of known aliases for an investor."""
    # INVESTOR_ALIAS maps alias → canonical.  Invert to find all aliases.
    canonical = INVESTOR_ALIAS.get(investor_name, investor_name)
    aliases = [k for k, v in INVESTOR_ALIAS.items() if v == canonical and k != investor_name]
    return aliases


def _calc_sharpe(pnl_pcts: list) -> float:
    """Rolling Sharpe ratio from a list of per-trade return percentages."""
    if len(pnl_pcts) < 2:
        return 0.0
    mean = sum(pnl_pcts) / len(pnl_pcts)
    variance = sum((x - mean) ** 2 for x in pnl_pcts) / (len(pnl_pcts) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    return round(mean / std, 4) if std > 0 else 0.0


def _calc_sortino(pnl_pcts: list) -> float:
    """Rolling Sortino ratio (only penalises downside deviation)."""
    if len(pnl_pcts) < 2:
        return 0.0
    mean = sum(pnl_pcts) / len(pnl_pcts)
    downside = [x for x in pnl_pcts if x < 0]
    if not downside:
        return round(mean / 0.01, 4) if mean > 0 else 0.0  # near-infinite → cap
    down_var = sum(x ** 2 for x in downside) / len(pnl_pcts)
    down_std = math.sqrt(down_var)
    return round(mean / down_std, 4) if down_std > 0 else 0.0


def _inline_ranking_scores(state: dict, metrics: dict) -> dict:
    """
    Compute the 4 ranking scores inline (same formulas as scoring_engine.py)
    so that monthly snapshots always have up-to-date scores.
    Returns dict with the 4 scores.
    """
    pm  = metrics.get("performance_metrics", {})
    cm  = metrics.get("conviction_metrics", {})
    csm = metrics.get("consistency_metrics", {})
    dna = state.get("behavioral_dna", {})
    identity = state.get("identity", {})

    total_trades        = pm.get("total_trades", 0)
    win_rate            = pm.get("win_rate", 0.0)
    profit_factor       = pm.get("profit_factor", 0.0)
    longest_win_streak  = csm.get("longest_win_streak", 0)
    max_drawdown_pct    = pm.get("max_drawdown_pct", 0.0)
    avg_profit_pct      = pm.get("avg_profit_pct", 0.0)
    avg_loss_pct        = pm.get("avg_loss_pct", 0.0)
    avg_hold_days       = cm.get("avg_hold_days", 0.0)
    avg_position_size   = cm.get("avg_position_size_pct", 0.0)
    entry_style         = dna.get("entry_style", "UNKNOWN")
    exit_style          = dna.get("exit_style", "UNKNOWN")
    investor_type       = identity.get("investor_type", "UNKNOWN")

    # Consistency Score
    w_wr = win_rate * 50.0
    w_pf = min(profit_factor, 3.0) / 3.0 * 30.0
    w_ws = min(longest_win_streak, 10) / 10.0 * 20.0
    consistency = w_wr + w_pf + w_ws

    # Risk Management Score
    w_dd = max(0.0, 50.0 - max_drawdown_pct)
    rr = (abs(avg_profit_pct / avg_loss_pct) if avg_loss_pct != 0
          else (3.0 if avg_profit_pct > 0 else 0.0))
    w_rr = min(rr, 3.0) / 3.0 * 30.0
    w_ex = 20.0 if exit_style == "GRADUAL" else 10.0
    risk_mgt = w_dd + w_rr + w_ex

    # Conviction Score
    w_hd = min(avg_hold_days, 180.0) / 180.0 * 50.0
    w_sz = min(avg_position_size * 100.0, 30.0)
    w_en = 20.0 if entry_style == "STAGGERED" else 10.0
    conviction = w_hd + w_sz + w_en

    # Smart Money Score
    # PENNY STOCK PROTECTION: Penalize 'OPERATOR's (manipulators) instead of rewarding them.
    if investor_type == "LARGE_INVESTOR":
        scale_bonus = 20.0
    elif investor_type == "MID_INVESTOR":
        scale_bonus = 10.0
    elif investor_type == "OPERATOR":
        scale_bonus = -50.0  # Heavy penalty for penny stock manipulators
    else:
        scale_bonus = 0.0
        
    smart_money = (consistency * 0.35) + (risk_mgt * 0.35) + (conviction * 0.1) + scale_bonus

    # Low volume dampener
    if total_trades < 3:
        consistency = min(consistency, 50.0)
        risk_mgt    = min(risk_mgt, 50.0)
        conviction  = min(conviction, 50.0)
        smart_money = min(smart_money, 50.0)

    return {
        "smart_money_score":       round(min(smart_money, 99.9), 2),
        "consistency_score":       round(min(consistency, 99.9), 2),
        "conviction_score":        round(min(conviction, 99.9), 2),
        "risk_management_score":   round(min(risk_mgt, 99.9), 2),
    }


# ---------------------------------------------------------------------------
# Helper: rolling / cumulative stats
# ---------------------------------------------------------------------------
def _eval_investor_type(cumulative: dict) -> str:
    """
    Evaluate investor type based on cumulative metrics accumulated so far.
    cumulative keys:
        total_trades, total_trade_value, penny_trade_count,
        large_trade_count, total_realized_pnl
    """
    n = cumulative["total_trades"]
    if n == 0:
        return "UNKNOWN"

    avg_trade_val  = cumulative["total_trade_value"] / n
    penny_ratio    = cumulative["penny_trade_count"] / n

    if avg_trade_val >= LARGE_TRADE_VALUE and penny_ratio >= OPERATOR_PENNY_RATIO:
        return "OPERATOR"
    if avg_trade_val >= LARGE_INVESTOR_AVG:
        return "LARGE_INVESTOR"
    if avg_trade_val < SMALL_INVESTOR_AVG:
        return "SMALL_INVESTOR"
    if SMALL_INVESTOR_AVG <= avg_trade_val < LARGE_INVESTOR_AVG:
        return "MID_INVESTOR"
    return "MIXED"


def _entry_style(scale_in_counts: list) -> str:
    """STAGGERED if avg buys-per-position > 1.5 else LUMP_SUM."""
    if not scale_in_counts:
        return "UNKNOWN"
    avg = sum(scale_in_counts) / len(scale_in_counts)
    return "STAGGERED" if avg >= 1.5 else "LUMP_SUM"


def _exit_style(scale_out_counts: list) -> str:
    """GRADUAL if avg sells-per-position > 1.5 else ALL_AT_ONCE."""
    if not scale_out_counts:
        return "UNKNOWN"
    avg = sum(scale_out_counts) / len(scale_out_counts)
    return "GRADUAL" if avg >= 1.5 else "ALL_AT_ONCE"


def _safe_float(val):
    """Convert Decimal or any numeric type to float."""
    if isinstance(val, Decimal):
        return float(val)
    return float(val) if val is not None else 0.0


class IngestProcessor:
    PAUSED = False

    def __init__(self, txn_df: pd.DataFrame, events_df: pd.DataFrame = None, file_hash: str = None):
        self.file_hash = file_hash
        getcontext().prec = 28  # High precision for money arithmetic

        # Sort chronologically: same-date BUY always before SELL
        txn_df = txn_df.copy()
        txn_df["_sort_type"] = txn_df["transaction_type"].map({"BUY": 0, "SELL": 1})
        self.txn_df = txn_df.sort_values(by=["date", "_sort_type"]).reset_index(drop=True)
        self.txn_df.drop(columns=["_sort_type"], inplace=True)

        if events_df is not None and not events_df.empty:
            self.events_df = events_df.sort_values(by="ex_date").reset_index(drop=True)
        else:
            self.events_df = pd.DataFrame()

        # In-memory caches (avoids repeated DB lookups)
        self.investor_states   = {}   # investor_name → investors doc
        self.investor_metrics  = {}   # investor_name → investor_metrics doc
        self.investor_cumul    = {}   # investor_name → cumulative stats dict

    # -----------------------------------------------------------------------
    # State initialisation helpers
    # -----------------------------------------------------------------------
    def _get_investor_state(self, investor_name: str, first_seen: date) -> dict:
        if investor_name not in self.investor_states:
            doc = investors_collection.find_one({"_id": investor_name})
            if not doc:
                doc = {
                    "_id": investor_name,
                    "identity": {
                        "name": investor_name,
                        "aliases": _get_aliases(investor_name),
                        "investor_type": "UNKNOWN",
                        "first_seen_date": first_seen.isoformat(),
                        "last_activity_date": first_seen.isoformat(),
                    },
                    "portfolio_state": {
                        "tracked_value": 0.0,
                        "positions": [],
                        "open_lots": [],
                    },
                    "ranking_scores": {
                        "smart_money_score": 0.0,
                        "consistency_score": 0.0,
                        "conviction_score": 0.0,
                        "risk_management_score": 0.0,
                    },
                    "activity_metrics": {
                        "last_trade_date": first_seen.isoformat(),
                        "last_buy_date": None,
                        "active_positions": 0,
                        "total_positions_traded": 0,
                        "total_buys": 0,
                        "total_sells": 0,
                    },
                    "behavioral_dna": {
                        "entry_style": "UNKNOWN",
                        "exit_style": "UNKNOWN",
                        "dip_buying_score": 0.0,
                        "trend_following_score": 0.0,
                        "preferred_mcap": "UNKNOWN",
                        "favorite_sector": "UNCLASSIFIED",
                        "avg_add_on_buy": 0.0,
                        "avg_reduce_on_sell": 0.0,
                    },
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                    },
                }
            self.investor_states[investor_name] = doc
        return self.investor_states[investor_name]

    def _get_investor_metrics(self, investor_name: str) -> dict:
        if investor_name not in self.investor_metrics:
            doc = investor_metrics_collection.find_one({"investor_id": investor_name})
            if not doc:
                doc = {
                    "investor_id": investor_name,
                    "performance_metrics": {
                        "total_trades": 0,
                        "total_buys": 0,
                        "total_sells": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "win_rate": 0.0,
                        "total_realized_pnl": 0.0,
                        "avg_return_pct": 0.0,
                        "median_return_pct": 0.0,
                        "avg_profit_pct": 0.0,
                        "avg_loss_pct": 0.0,
                        "profit_factor": 0.0,
                        "expectancy": 0.0,
                        "max_drawdown_pct": 0.0,
                    },
                    "conviction_metrics": {
                        "avg_position_size_pct": 0.0,
                        "max_position_size_pct": 0.0,
                        "avg_scale_in_count": 0.0,
                        "avg_scale_out_count": 0.0,
                        "avg_hold_days": 0.0,
                        "median_hold_days": 0.0,
                        "min_hold_days": 0,
                        "max_hold_days": 0,
                        "long_hold_ratio": 0.0,
                    },
                    "consistency_metrics": {
                        "profitable_years": 0,
                        "loss_years": 0,
                        "longest_win_streak": 0,
                        "longest_loss_streak": 0,
                        "current_win_streak": 0,
                        "current_loss_streak": 0,
                        "rolling_sharpe_ratio": 0.0,
                        "rolling_sortino_ratio": 0.0,
                    },
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                    },
                }
            self.investor_metrics[investor_name] = doc
        return self.investor_metrics[investor_name]

    def _get_cumulative(self, investor_name: str) -> dict:
        if investor_name not in self.investor_cumul:
            self.investor_cumul[investor_name] = {
                "total_trades": 0,
                "total_trade_value": 0.0,
                "penny_trade_count": 0,
                "large_trade_count": 0,
                "total_realized_pnl": 0.0,
                # For running profit factor
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                # For avg/median hold days
                "all_hold_days": [],
                # For PnL % per trade (sell only)
                "all_pnl_pct": [],
                # Streak tracking
                "current_win_streak": 0,
                "current_loss_streak": 0,
                "longest_win_streak": 0,
                "longest_loss_streak": 0,
                # Year-level P&L tracking  {year: pnl_sum}
                "year_pnl": {},
                # scale_in/out tracking per symbol
                "buy_counts_per_position": {},    # symbol → buy count for current open position
                "sell_counts_per_position": {},   # symbol → sell count for current open position
                "closed_scale_in": [],            # history of scale_in counts for closed positions
                "closed_scale_out": [],           # history of scale_out counts for closed positions
                # For max drawdown: track running peak portfolio value
                "peak_portfolio_value": 0.0,
                "max_drawdown_pct": 0.0,
                # --- NEW: trade sequence counter (per investor) ---
                "trade_sequence_counter": 0,
                # --- NEW: per-symbol max transaction price (for peak_price_during_hold) ---
                "symbol_max_price": {},           # symbol → max price seen across all txns
                # --- NEW: mcap category tracking ---
                "mcap_counts": {},                # mcap_category → count
                # --- NEW: sector tracking ---
                "sector_counts": {},              # sector → count
                # --- NEW: dip-buying / trend-following tracking ---
                "symbol_avg_price": {},           # symbol → running average price
                "symbol_price_count": {},         # symbol → count of prices seen
                "dip_buy_count": 0,               # buys at price < running avg
                "trend_buy_count": 0,             # buys at price > running avg
                "total_buy_count": 0,             # total buys (for ratio calc)
            }
        return self.investor_cumul[investor_name]

    # -----------------------------------------------------------------------
    # Portfolio helpers
    # -----------------------------------------------------------------------
    def _get_position(self, state: dict, symbol: str) -> dict:
        for pos in state["portfolio_state"]["positions"]:
            if pos["symbol"] == symbol:
                return pos
        pos = {
            "symbol": symbol,
            "qty": 0,
            "avg_price": 0.0,
            "first_buy_date": None,
            "last_buy_date": None,
            "position_weight": 0.0,
        }
        state["portfolio_state"]["positions"].append(pos)
        return pos

    def _get_open_lots(self, state: dict, symbol: str) -> list:
        return [lot for lot in state["portfolio_state"]["open_lots"] if lot["symbol"] == symbol]

    def _replace_open_lots(self, state: dict, symbol: str, updated_lots: list):
        state["portfolio_state"]["open_lots"] = [
            lot for lot in state["portfolio_state"]["open_lots"] if lot["symbol"] != symbol
        ]
        state["portfolio_state"]["open_lots"].extend(updated_lots)

    def _recalc_position_from_lots(self, pos: dict, open_lots: list):
        total_qty = sum(lot["qty"] for lot in open_lots)
        if total_qty > 0:
            total_cost = sum(
                Decimal(str(lot["qty"])) * Decimal(str(lot["price"])) for lot in open_lots
            )
            pos["qty"] = total_qty
            pos["avg_price"] = _safe_float(total_cost / Decimal(str(total_qty)))
        else:
            pos["qty"] = 0
            pos["avg_price"] = 0.0

    def _calc_tracked_value(self, state: dict) -> float:
        """Sum of strict cost basis across all open lots to prevent float drift."""
        total_value = Decimal("0")
        for lot in state["portfolio_state"]["open_lots"]:
            total_value += Decimal(str(lot["qty"])) * Decimal(str(lot["price"]))
        return float(total_value)

    def _update_position_weights(self, state: dict):
        tracked = self._calc_tracked_value(state)
        state["portfolio_state"]["tracked_value"] = tracked
        for pos in state["portfolio_state"]["positions"]:
            if tracked > 0 and pos["qty"] > 0:
                pos["position_weight"] = round((pos["qty"] * pos["avg_price"]) / tracked, 6)
            else:
                pos["position_weight"] = 0.0

    def _hold_days_from_lots(self, lots: list, ref_date: date) -> tuple:
        """Return (min_hold_days, max_hold_days) derived from open_lots buy_date."""
        if not lots:
            return 0, 0
        days_list = [(ref_date - datetime.fromisoformat(lot["buy_date"]).date()).days for lot in lots]
        return min(days_list), max(days_list)

    # -----------------------------------------------------------------------
    # Investor classification (called on every row)
    # -----------------------------------------------------------------------
    def _classify_investor(self, cumul: dict, state: dict):
        investor_type = _eval_investor_type(cumul)
        state["identity"]["investor_type"] = investor_type

    # -----------------------------------------------------------------------
    # Metrics updaters
    # -----------------------------------------------------------------------
    def _update_metrics_on_buy(self, investor_name: str, symbol: str, qty: int, price: Decimal, txn_date: date):
        cumul   = self._get_cumulative(investor_name)
        metrics = self._get_investor_metrics(investor_name)
        state   = self.investor_states[investor_name]

        trade_value = float(qty) * float(price)

        EXEMPT_LOW_PRICE_STOCKS = {
            "IDEA", "YESBANK", "SUZLON", "IRFC", "PNB", "IDFCFIRSTB", 
            "UCOBANK", "BANKINDIA", "UNIONBANK", "IOB", "NHPC", "SJVN", 
            "CENTRALBK", "MAHABANK", "EQUITASBNK", "UJJIVANSFB", "SOUTHBANK",
            "GMRINFRA", "JPPOWER", "RPOWER", "RTNPOWER", "INFIBEAM", "HCC", 
            "TRIDENT", "NBCC", "RENUKA", "EASEMYTRIP", "ZOMATO"
        }

        # Cumulative counters
        cumul["total_trades"]      += 1
        cumul["total_trade_value"] += trade_value
        if float(price) < PENNY_PRICE_THRESHOLD and symbol not in EXEMPT_LOW_PRICE_STOCKS:
            cumul["penny_trade_count"] += 1
        if trade_value > LARGE_TRADE_VALUE:
            cumul["large_trade_count"] += 1

        # Track buy count for this symbol (scale-in)
        cumul["buy_counts_per_position"][symbol] = cumul["buy_counts_per_position"].get(symbol, 0) + 1

        # Performance metrics
        pm = metrics["performance_metrics"]
        pm["total_trades"] += 1
        pm["total_buys"]   += 1

        # --- NEW: dip-buying / trend-following detection ---
        fprice = float(price)
        cumul["total_buy_count"] += 1
        running_avg = cumul["symbol_avg_price"].get(symbol)
        if running_avg is not None:
            if fprice < running_avg:
                cumul["dip_buy_count"] += 1
            elif fprice > running_avg:
                cumul["trend_buy_count"] += 1
        # Update running average for this symbol
        prev_count = cumul["symbol_price_count"].get(symbol, 0)
        prev_avg   = cumul["symbol_avg_price"].get(symbol, 0.0)
        new_count  = prev_count + 1
        cumul["symbol_avg_price"][symbol]   = (prev_avg * prev_count + fprice) / new_count
        cumul["symbol_price_count"][symbol] = new_count

        # --- NEW: track max price per symbol (for peak_price_during_hold) ---
        cumul["symbol_max_price"][symbol] = max(cumul["symbol_max_price"].get(symbol, 0.0), fprice)

        # --- NEW: mcap + sector tracking ---
        mcap_cat = _classify_mcap(fprice)
        cumul["mcap_counts"][mcap_cat] = cumul["mcap_counts"].get(mcap_cat, 0) + 1
        sector = _get_sector(symbol)
        cumul["sector_counts"][sector] = cumul["sector_counts"].get(sector, 0) + 1

        # --- NEW: Update behavioral DNA on buy (so buy-only investors get profiled too) ---
        if cumul["total_buy_count"] > 0:
            state["behavioral_dna"]["dip_buying_score"]     = round(cumul["dip_buy_count"] / cumul["total_buy_count"], 4)
            state["behavioral_dna"]["trend_following_score"] = round(cumul["trend_buy_count"] / cumul["total_buy_count"], 4)
        if cumul["mcap_counts"]:
            state["behavioral_dna"]["preferred_mcap"] = max(cumul["mcap_counts"], key=cumul["mcap_counts"].get)
        if cumul["sector_counts"]:
            state["behavioral_dna"]["favorite_sector"] = max(cumul["sector_counts"], key=cumul["sector_counts"].get)

        # --- NEW: Inline ranking scores on buy (keeps scores always fresh) ---
        scores = _inline_ranking_scores(state, metrics)
        state["ranking_scores"] = scores

        # Activity
        state["activity_metrics"]["total_buys"] += 1

    def _update_metrics_on_sell(
        self,
        investor_name: str,
        symbol: str,
        qty: int,
        price: Decimal,
        pnl_amount: float,
        pnl_pct: float,
        min_hold: int,
        max_hold: int,
        exit_type: str,
        txn_date: date,
        position_closed: bool,
    ):
        cumul   = self._get_cumulative(investor_name)
        metrics = self._get_investor_metrics(investor_name)
        state   = self.investor_states[investor_name]

        trade_value = float(qty) * float(price)

        EXEMPT_LOW_PRICE_STOCKS = {
            "IDEA", "YESBANK", "SUZLON", "IRFC", "PNB", "IDFCFIRSTB", 
            "UCOBANK", "BANKINDIA", "UNIONBANK", "IOB", "NHPC", "SJVN", 
            "CENTRALBK", "MAHABANK", "EQUITASBNK", "UJJIVANSFB", "SOUTHBANK",
            "GMRINFRA", "JPPOWER", "RPOWER", "RTNPOWER", "INFIBEAM", "HCC", 
            "TRIDENT", "NBCC", "RENUKA", "EASEMYTRIP", "ZOMATO"
        }

        # Cumulative counters
        cumul["total_trades"]      += 1
        cumul["total_trade_value"] += trade_value
        if float(price) < PENNY_PRICE_THRESHOLD and symbol not in EXEMPT_LOW_PRICE_STOCKS:
            cumul["penny_trade_count"] += 1
        if trade_value > LARGE_TRADE_VALUE:
            cumul["large_trade_count"] += 1

        cumul["total_realized_pnl"] += pnl_amount
        cumul["all_pnl_pct"].append(pnl_pct)
        cumul["all_hold_days"].append(max_hold)   # max hold day for the sold tranche

        # Win / loss streak
        if pnl_amount >= 0:
            cumul["current_win_streak"]  += 1
            cumul["current_loss_streak"]  = 0
            cumul["gross_profit"]         += pnl_amount
        else:
            cumul["current_loss_streak"] += 1
            cumul["current_win_streak"]   = 0
            cumul["gross_loss"]           += abs(pnl_amount)

        cumul["longest_win_streak"]  = max(cumul["longest_win_streak"],  cumul["current_win_streak"])
        cumul["longest_loss_streak"] = max(cumul["longest_loss_streak"], cumul["current_loss_streak"])

        # Year P&L
        year = txn_date.year
        cumul["year_pnl"][year] = cumul["year_pnl"].get(year, 0.0) + pnl_amount

        # Track sell count for this symbol (scale-out)
        cumul["sell_counts_per_position"][symbol] = cumul["sell_counts_per_position"].get(symbol, 0) + 1

        # When position fully closed → record scale-in/out history
        if position_closed:
            bi = cumul["buy_counts_per_position"].pop(symbol, 1)
            si = cumul["sell_counts_per_position"].pop(symbol, 1)
            cumul["closed_scale_in"].append(bi)
            cumul["closed_scale_out"].append(si)

        # Activity
        state["activity_metrics"]["total_sells"] += 1

        # ---- Now derive full metrics from cumulative data ----
        pm  = metrics["performance_metrics"]
        cm  = metrics["conviction_metrics"]
        csm = metrics["consistency_metrics"]

        pm["total_trades"] += 1
        pm["total_sells"]  += 1

        if pnl_amount >= 0:
            pm["winning_trades"] += 1
        else:
            pm["losing_trades"]  += 1

        total_closed = pm["winning_trades"] + pm["losing_trades"]
        pm["win_rate"]          = round(pm["winning_trades"] / total_closed, 4) if total_closed > 0 else 0.0
        pm["total_realized_pnl"] = round(cumul["total_realized_pnl"], 2)

        all_pnl = cumul["all_pnl_pct"]
        pm["avg_return_pct"] = round(sum(all_pnl) / len(all_pnl), 4) if all_pnl else 0.0

        # Median
        sorted_pnl = sorted(all_pnl)
        n = len(sorted_pnl)
        if n > 0:
            mid = n // 2
            pm["median_return_pct"] = (sorted_pnl[mid] if n % 2 == 1
                                       else round((sorted_pnl[mid - 1] + sorted_pnl[mid]) / 2, 4))

        wins_pct  = [p for p in all_pnl if p >= 0]
        losses_pct = [p for p in all_pnl if p < 0]
        pm["avg_profit_pct"] = round(sum(wins_pct)   / len(wins_pct),    4) if wins_pct else 0.0
        pm["avg_loss_pct"]   = round(sum(losses_pct) / len(losses_pct), 4) if losses_pct else 0.0

        # Profit factor = gross_profit / gross_loss
        pm["profit_factor"] = round(cumul["gross_profit"] / cumul["gross_loss"], 4) if cumul["gross_loss"] > 0 else 0.0

        # Expectancy = (win_rate * avg_profit_pct) - (loss_rate * abs(avg_loss_pct))
        loss_rate = 1.0 - pm["win_rate"]
        pm["expectancy"] = round(
            (pm["win_rate"] * pm["avg_profit_pct"]) - (loss_rate * abs(pm["avg_loss_pct"])), 4
        )

        # Hold days
        all_hold = cumul["all_hold_days"]
        if all_hold:
            cm["avg_hold_days"]  = round(sum(all_hold) / len(all_hold), 2)
            cm["min_hold_days"]  = min(all_hold)
            cm["max_hold_days"]  = max(all_hold)
            sorted_hold = sorted(all_hold)
            nh = len(sorted_hold)
            midh = nh // 2
            cm["median_hold_days"] = (sorted_hold[midh] if nh % 2 == 1
                                      else round((sorted_hold[midh - 1] + sorted_hold[midh]) / 2, 2))
            cm["long_hold_ratio"] = round(sum(1 for d in all_hold if d >= 180) / len(all_hold), 4)

        # Scale-in / out averages (from closed positions history)
        if cumul["closed_scale_in"]:
            cm["avg_scale_in_count"]  = round(sum(cumul["closed_scale_in"])  / len(cumul["closed_scale_in"]),  2)
        if cumul["closed_scale_out"]:
            cm["avg_scale_out_count"] = round(sum(cumul["closed_scale_out"]) / len(cumul["closed_scale_out"]), 2)

        # Portfolio value and max drawdown
        tracked = self._calc_tracked_value(state)
        pf = cumul["peak_portfolio_value"]
        if tracked > pf:
            cumul["peak_portfolio_value"] = tracked
        elif pf > 0 and tracked < pf:
            dd = ((pf - tracked) / pf) * 100.0
            if dd > cumul["max_drawdown_pct"]:
                cumul["max_drawdown_pct"] = dd
        pm["max_drawdown_pct"] = round(cumul["max_drawdown_pct"], 4)

        # Consistency
        csm["current_win_streak"]  = cumul["current_win_streak"]
        csm["current_loss_streak"] = cumul["current_loss_streak"]
        csm["longest_win_streak"]  = cumul["longest_win_streak"]
        csm["longest_loss_streak"] = cumul["longest_loss_streak"]

        profitable_years = sum(1 for v in cumul["year_pnl"].values() if v >= 0)
        loss_years       = sum(1 for v in cumul["year_pnl"].values() if v < 0)
        csm["profitable_years"] = profitable_years
        csm["loss_years"]       = loss_years

        # Behavioral DNA update
        state["behavioral_dna"]["entry_style"] = _entry_style(cumul["closed_scale_in"])
        state["behavioral_dna"]["exit_style"]  = _exit_style(cumul["closed_scale_out"])

        # avg_add_on_buy / avg_reduce_on_sell (based on scale-in/out averages)
        state["behavioral_dna"]["avg_add_on_buy"]      = cm["avg_scale_in_count"]
        state["behavioral_dna"]["avg_reduce_on_sell"]  = cm["avg_scale_out_count"]

        # Conviction metrics: max_position_size_pct and avg_position_size_pct
        tracked_val = state["portfolio_state"]["tracked_value"]
        if tracked_val > 0:
            for pos in state["portfolio_state"]["positions"]:
                if pos["qty"] > 0:
                    weight = pos["position_weight"]
                    if weight > cm["max_position_size_pct"]:
                        cm["max_position_size_pct"] = round(weight, 6)

        # Simple moving avg for position size
        active_count = sum(1 for p in state["portfolio_state"]["positions"] if p["qty"] > 0)
        if active_count > 0:
            cm["avg_position_size_pct"] = round(1.0 / active_count, 6)

        # --- NEW: Rolling Sharpe & Sortino ratios ---
        csm["rolling_sharpe_ratio"]  = _calc_sharpe(cumul["all_pnl_pct"])
        csm["rolling_sortino_ratio"] = _calc_sortino(cumul["all_pnl_pct"])

        # --- NEW: sell-side price tracking (for peak_price_during_hold) ---
        fprice = float(price)
        cumul["symbol_max_price"][symbol] = max(cumul["symbol_max_price"].get(symbol, 0.0), fprice)

        # --- NEW: sell-side mcap + sector tracking ---
        mcap_cat = _classify_mcap(fprice)
        cumul["mcap_counts"][mcap_cat] = cumul["mcap_counts"].get(mcap_cat, 0) + 1
        sector = _get_sector(symbol)
        cumul["sector_counts"][sector] = cumul["sector_counts"].get(sector, 0) + 1

        # --- NEW: update running avg price for this symbol ---
        prev_count = cumul["symbol_price_count"].get(symbol, 0)
        prev_avg   = cumul["symbol_avg_price"].get(symbol, 0.0)
        new_count  = prev_count + 1
        cumul["symbol_avg_price"][symbol]   = (prev_avg * prev_count + fprice) / new_count
        cumul["symbol_price_count"][symbol] = new_count

        # --- NEW: Behavioral DNA — dip_buying, trend_following, preferred_mcap, favorite_sector ---
        total_buys = cumul["total_buy_count"]
        if total_buys > 0:
            state["behavioral_dna"]["dip_buying_score"]      = round(cumul["dip_buy_count"] / total_buys, 4)
            state["behavioral_dna"]["trend_following_score"]  = round(cumul["trend_buy_count"] / total_buys, 4)

        # preferred_mcap = most frequent mcap category across all trades
        if cumul["mcap_counts"]:
            state["behavioral_dna"]["preferred_mcap"] = max(cumul["mcap_counts"], key=cumul["mcap_counts"].get)

        # favorite_sector = most frequent sector across all trades
        if cumul["sector_counts"]:
            state["behavioral_dna"]["favorite_sector"] = max(cumul["sector_counts"], key=cumul["sector_counts"].get)

        # --- NEW: Inline ranking scores (keeps snapshots up to date) ---
        scores = _inline_ranking_scores(state, metrics)
        state["ranking_scores"] = scores

        metrics["metadata"]["last_updated"] = datetime.now().isoformat()

    # -----------------------------------------------------------------------
    # Main Execution Loop
    # -----------------------------------------------------------------------
    def run(self, start_row: int = 0):
        import time
        start_exec_time   = time.time()
        processed_cnt     = 0
        last_processed_dt = {}  # symbol → last processed date (for corporate action gating)

        current_month = None
        total_rows    = len(self.txn_df)

        self.pg_conn = get_connection()
        try:
            yield f"[INFO] Starting synchronous row-by-row processing for {total_rows} rows..."

            # Warm up investor states + metrics from MongoDB
            for doc in investors_collection.find({}):
                self.investor_states[doc["_id"]] = doc
            for doc in investor_metrics_collection.find({}):
                self.investor_metrics[doc["investor_id"]] = doc
            yield f"[INFO] Pre-loaded {len(self.investor_states)} investor states from MongoDB cache."

            if start_row > 0:
                yield f"[INFO] Resuming from row index {start_row}..."

            for idx, row in self.txn_df.iterrows():
                while IngestProcessor.PAUSED:
                    import time
                    time.sleep(1)

                if idx < start_row:
                    continue

                investor_name = row["investor_name"]
                symbol        = row["stock_symbol"]
                txn_date      = row["date"]
                txn_type      = row["transaction_type"]
                qty           = int(row["quantity"])
                price         = Decimal(str(row["price"]))
                processed_cnt += 1

                # ETA
                elapsed = time.time() - start_exec_time
                eta_str = "Calculating..."
                if processed_cnt > 5 and elapsed > 0:
                    rows_per_sec   = processed_cnt / elapsed
                    remaining      = total_rows - (idx + 1)
                    eta_secs       = max(0, remaining / rows_per_sec)
                    hrs  = int(eta_secs // 3600)
                    mins = int((eta_secs % 3600) // 60)
                    secs = int(eta_secs % 60)
                    eta_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"

                pct = int(((idx + 1) / total_rows) * 100)
                yield f"[PROGRESS|{pct}] Row {idx+1}/{total_rows} | {txn_date} | E.T.A: {eta_str} | {investor_name} | {symbol}"

                # Month boundary → persist snapshots for ended months
                if current_month is None:
                    current_month = txn_date
                while (current_month.year < txn_date.year or
                       (current_month.year == txn_date.year and current_month.month < txn_date.month)):
                    last_day        = calendar.monthrange(current_month.year, current_month.month)[1]
                    end_of_month    = date(current_month.year, current_month.month, last_day)
                    
                    # STORAGE OPTIMIZATION: Only take yearly snapshots (December) for historical data
                    # Take monthly snapshots only for the current and previous year to save NeonDB space.
                    current_year = date.today().year
                    if current_month.month == 12 or current_month.year >= current_year - 1:
                        yield from self._sync_persist_monthly_snapshots(end_of_month)
                        
                    if current_month.month == 12:
                        current_month = date(current_month.year + 1, 1, 1)
                    else:
                        current_month = date(current_month.year, current_month.month + 1, 1)
                current_month = txn_date

                # Fetch or initialise investor state
                state   = self._get_investor_state(investor_name, txn_date)
                metrics = self._get_investor_metrics(investor_name)
                cumul   = self._get_cumulative(investor_name)
                pos     = self._get_position(state, symbol)
                lots    = self._get_open_lots(state, symbol)

                # Corporate actions before processing row
                if not self.events_df.empty:
                    last_dt      = last_processed_dt.get(symbol, date.min)
                    mask         = (
                        (self.events_df["stock_symbol"] == symbol) &
                        (self.events_df["ex_date"] > last_dt) &
                        (self.events_df["ex_date"] <= txn_date)
                    )
                    pending_evts = self.events_df[mask].to_dict("records")
                    if pending_evts:
                        lots, requires_liquidation = process_corporate_actions(lots, pending_evts)
                        self._replace_open_lots(state, symbol, lots)
                        self._recalc_position_from_lots(pos, lots)
                        
                        if requires_liquidation:
                            yield f"[EVENT] [TEMPORARY LOGIC] Liquidating {symbol} for {investor_name} due to Merger/Demerger."
                last_processed_dt[symbol] = txn_date

                # Update last activity
                state["identity"]["last_activity_date"]      = txn_date.isoformat()
                state["activity_metrics"]["last_trade_date"] = txn_date.isoformat()

                sell_rec = None

                # ----------------------------------------------------------------
                # BUY
                # ----------------------------------------------------------------
                if txn_type == "BUY":
                    lots.append({
                        "symbol":   symbol,
                        "qty":      qty,
                        "price":    float(price),
                        "buy_date": txn_date.isoformat(),
                    })
                    self._replace_open_lots(state, symbol, lots)
                    self._recalc_position_from_lots(pos, lots)
                    state["activity_metrics"]["last_buy_date"] = txn_date.isoformat()

                    # --- NEW: update position buy dates ---
                    date_iso = txn_date.isoformat()
                    if not pos.get("first_buy_date") or date_iso < pos["first_buy_date"]:
                        pos["first_buy_date"] = date_iso
                    pos["last_buy_date"] = date_iso

                    self._update_metrics_on_buy(investor_name, symbol, qty, price, txn_date)

                # ----------------------------------------------------------------
                # SELL (FIFO lot matching)
                # ----------------------------------------------------------------
                elif txn_type == "SELL":
                    open_qty = pos["qty"]
                    if qty > open_qty:
                        warning = (f"[WARN] Short sell guard: {investor_name} tried to sell {qty} "
                                   f"of {symbol} but only {open_qty} held. Clipped to {open_qty}.")
                        yield f"[EVENT] {warning}"
                        sell_to_process = open_qty
                    else:
                        sell_to_process = qty

                    if sell_to_process > 0:
                        total_pnl  = Decimal("0")
                        total_cost = Decimal("0")
                        lots_used  = 0
                        remaining  = sell_to_process
                        min_hold   = 999_999
                        max_hold   = -1
                        first_buy  = None
                        last_buy   = None
                        new_lots   = []

                        for lot in lots:
                            if remaining <= 0:
                                new_lots.append(lot)
                                continue
                            buy_date_obj = datetime.fromisoformat(lot["buy_date"]).date()
                            hold_days    = (txn_date - buy_date_obj).days
                            min_hold     = min(min_hold, hold_days)
                            max_hold     = max(max_hold, hold_days)
                        
                            if first_buy is None or buy_date_obj < first_buy:
                                first_buy = buy_date_obj
                            if last_buy is None or buy_date_obj > last_buy:
                                last_buy = buy_date_obj

                            qty_in_lot   = Decimal(str(lot["qty"]))
                            lot_price    = Decimal(str(lot["price"]))

                            if qty_in_lot <= remaining:
                                qty_sold   = qty_in_lot
                                remaining -= int(qty_in_lot)
                                lots_used += 1
                                total_cost += qty_sold * lot_price
                                total_pnl  += qty_sold * (price - lot_price)
                            else:
                                qty_sold         = Decimal(str(remaining))
                                lot["qty"]      -= remaining
                                remaining        = 0
                                lots_used       += 1
                                total_cost      += qty_sold * lot_price
                                total_pnl       += qty_sold * (price - lot_price)
                                new_lots.append(lot)

                        self._replace_open_lots(state, symbol, new_lots)
                        remaining_lots = [l for l in new_lots if l["symbol"] == symbol]
                        self._recalc_position_from_lots(pos, remaining_lots)

                        pnl_pct    = float((total_pnl / total_cost) * 100) if total_cost > 0 else 0.0
                        entry_type = "MULTIPLE_LOTS" if lots_used > 1 else "SINGLE_LOT"
                        exit_type  = "PARTIAL" if pos["qty"] > 0 else "FULL"
                        position_closed = (exit_type == "FULL")

                        if min_hold == 999_999:
                            min_hold = 0

                        # --- NEW: populate previously-dead sell_rec fields ---
                        cumul["trade_sequence_counter"] += 1
                        _trade_seq = cumul["trade_sequence_counter"]
                        _peak_price = cumul["symbol_max_price"].get(symbol)
                        _mcap_cat = _classify_mcap(float(price))

                        # INTRADAY PROTECTION: Ignore trades where buy and sell occurred on the exact same day
                        if max_hold > 0:
                            sell_rec = (
                                investor_name, symbol, txn_date, sell_to_process, float(price),
                                float(total_pnl), pnl_pct, min_hold, max_hold,
                                first_buy.isoformat() if first_buy else None, 
                                last_buy.isoformat() if last_buy else None,
                                _trade_seq, exit_type, entry_type, _peak_price, _mcap_cat
                            )

                            self._update_metrics_on_sell(
                                investor_name, symbol, sell_to_process, price,
                                float(total_pnl), pnl_pct, min_hold, max_hold,
                                exit_type, txn_date, position_closed
                            )

                # Update tracked_value + position weights after every row
                self._update_position_weights(state)

                # Re-classify investor type on every row
                self._classify_investor(cumul, state)

                # Active positions count
                active_count = sum(1 for p in state["portfolio_state"]["positions"] if p["qty"] > 0)
                state["activity_metrics"]["active_positions"]        = active_count
                state["activity_metrics"]["total_positions_traded"]  = len(state["portfolio_state"]["positions"])

                # Persist row to both DBs
                self._sync_persist_row(idx, investor_name, txn_date, state, sell_rec)

            # Final month snapshot - only if we reached the actual end of the month in this batch
            if current_month is not None:
                last_day     = calendar.monthrange(current_month.year, current_month.month)[1]
                if txn_date.day == last_day:
                    end_of_month = date(current_month.year, current_month.month, last_day)
                    yield from self._sync_persist_monthly_snapshots(end_of_month)

            yield "[STAGE] Pipeline complete. All rows processed and persisted synchronously."
        
        finally:
            if hasattr(self, "pg_conn") and self.pg_conn:
                self.pg_conn.close()

    # -----------------------------------------------------------------------
    # Persistence helpers
    # -----------------------------------------------------------------------
    def _sanitize(self, obj):
        """Recursively convert Decimal → float so MongoDB doesn't reject docs."""
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        return obj

    def _sync_persist_row(self, row_idx, investor_id, txn_date, state, sell_rec):
        """Commit everything for this row to PostgreSQL and MongoDB."""
        state["metadata"]["last_updated"] = datetime.now().isoformat()

        # 1. MongoDB – investors
        sanitized_state = self._sanitize(state)
        investors_collection.replace_one({"_id": investor_id}, sanitized_state, upsert=True)

        # 2. MongoDB – investor_metrics
        if investor_id in self.investor_metrics:
            m_doc = self._sanitize(self.investor_metrics[investor_id])
            investor_metrics_collection.replace_one({"investor_id": investor_id}, m_doc, upsert=True)

        # 3. PostgreSQL – sell_transactions + checkpoint
        with self.pg_conn.cursor() as cur:
            if sell_rec:
                cur.execute(
                    """
                    INSERT INTO sell_transactions (
                        client_id, symbol, sell_date, sell_quantity, sell_price,
                        pnl_amount, pnl_percentage, min_hold_duration, max_hold_duration,
                        first_buy_date, last_buy_date,
                        trade_sequence, exit_type, entry_type, peak_price_during_hold, mcap_category
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    sell_rec,
                )
            if self.file_hash:
                cur.execute(
                    """
                    INSERT INTO ingestion_status (file_hash, last_row_index, last_processed_date, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (file_hash) DO UPDATE SET
                        last_row_index = EXCLUDED.last_row_index,
                        last_processed_date = EXCLUDED.last_processed_date,
                        updated_at = NOW()
                    """,
                    (self.file_hash, row_idx, txn_date),
                )
        self.pg_conn.commit()

    def _sync_persist_monthly_snapshots(self, target_date: date):
        """End-of-month snapshot: reads latest metrics from memory and flushes to Postgres."""
        yield f"[INFO] [SYNC] Capturing monthly snapshots for {target_date}..."
        records = []
        for inv_id, inv in self.investor_states.items():
            rankings  = inv.get("ranking_scores", {})
            behavior  = inv.get("behavioral_dna", {})
            active_ct = sum(1 for p in inv["portfolio_state"]["positions"] if p["qty"] > 0)
            # Pull performance from metrics cache
            m   = self.investor_metrics.get(inv_id, {})
            pm  = m.get("performance_metrics", {})
            cm  = m.get("conviction_metrics", {})
            records.append((
                inv_id, target_date,
                rankings.get("smart_money_score", 0.0),
                rankings.get("consistency_score", 0.0),
                rankings.get("conviction_score", 0.0),
                rankings.get("risk_management_score", 0.0),
                pm.get("total_trades", 0),
                pm.get("win_rate", 0.0),
                pm.get("avg_return_pct", 0.0),
                pm.get("profit_factor", 0.0),
                pm.get("max_drawdown_pct", 0.0),
                pm.get("total_realized_pnl", 0.0),
                active_ct,
                cm.get("avg_hold_days", 0.0),
                behavior.get("entry_style", "UNKNOWN"),
                behavior.get("exit_style", "UNKNOWN"),
                behavior.get("preferred_mcap", "UNKNOWN"),
                behavior.get("favorite_sector", "UNCLASSIFIED"),
            ))

        if records:
            with self.pg_conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO investor_snapshots (
                        investor_id, snapshot_date,
                        smart_money_score, consistency_score, conviction_score, risk_management_score,
                        total_trades, win_rate, avg_return_pct, profit_factor,
                        max_drawdown_pct, total_realized_pnl,
                        active_positions, avg_hold_days,
                        entry_style, exit_style, preferred_mcap, favorite_sector
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (investor_id, snapshot_date) DO UPDATE SET
                        smart_money_score     = EXCLUDED.smart_money_score,
                        consistency_score     = EXCLUDED.consistency_score,
                        conviction_score      = EXCLUDED.conviction_score,
                        risk_management_score = EXCLUDED.risk_management_score,
                        total_trades          = EXCLUDED.total_trades,
                        win_rate              = EXCLUDED.win_rate,
                        avg_return_pct        = EXCLUDED.avg_return_pct,
                        profit_factor         = EXCLUDED.profit_factor,
                        max_drawdown_pct      = EXCLUDED.max_drawdown_pct,
                        total_realized_pnl    = EXCLUDED.total_realized_pnl,
                        active_positions      = EXCLUDED.active_positions,
                        avg_hold_days         = EXCLUDED.avg_hold_days,
                        entry_style           = EXCLUDED.entry_style,
                        exit_style            = EXCLUDED.exit_style,
                        preferred_mcap        = EXCLUDED.preferred_mcap,
                        favorite_sector       = EXCLUDED.favorite_sector,
                        created_at            = NOW()
                    """,
                    records,
                )
            self.pg_conn.commit()
        yield f"[INFO] [SYNC] {len(records)} monthly snapshots persisted to PostgreSQL."

    @staticmethod
    def get_checkpoint(file_hash: str) -> int:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT last_row_index FROM ingestion_status WHERE file_hash = %s;", (file_hash,))
                    row = cur.fetchone()
                    return row[0] if row else -1
        except Exception:
            return -1
