"""
Trade candidate data model.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TradeCandidate:
    """
    Represents an already-generated candidate trade proposed for capital allocation.

    Required Fields:
        symbol (str): Target symbol or pair (e.g. 'AAPL', 'EURUSD').
        asset_class (str): Asset class ('equity', 'forex', 'crypto', etc.).
        side (str): Direction ('long' or 'short').
        entry_price (float): Proposed entry price.
        proposed_stop_price (float): Proposed stop loss price level.
        strategy_id (str): Strategy identifier proposing this trade.

    Optional Fields:
        atr (Optional[float]): Current ATR value for the asset.
        atr_ratio (Optional[float]): Ratio of current ATR to historical reference ATR.
        volatility (Optional[float]): Asset historical volatility.
        sector (Optional[str]): Equity sector classification.
        country (Optional[str]): Country classification.
        currency_exposure (Optional[Dict[str, float]]): Factor currency exposure weights.
        beta (Optional[float]): Asset market beta.
        expected_slippage (Optional[float]): Estimated slippage per unit/share.
        commission (Optional[float]): Expected fixed or per-unit commission cost.
        spread (Optional[float]): Current bid-ask spread.
        pip_value_per_lot (Optional[float]): Monetary pip value for 1 standard lot (FX).
        lot_size (Optional[float]): Base units per lot (default 100,000 for standard FX lot).
        point_value (Optional[float]): Monetary value per point move per unit/contract.
    """
    symbol: str
    asset_class: str
    side: str
    entry_price: float
    proposed_stop_price: float
    strategy_id: str

    atr: Optional[float] = None
    atr_ratio: Optional[float] = None
    volatility: Optional[float] = None
    sector: Optional[str] = None
    country: Optional[str] = None
    currency_exposure: Optional[Dict[str, float]] = None
    beta: Optional[float] = None
    expected_slippage: Optional[float] = None
    commission: Optional[float] = None
    spread: Optional[float] = None
    pip_value_per_lot: Optional[float] = None
    lot_size: Optional[float] = None
    point_value: Optional[float] = None

    # Conviction Parameters (supports scalar float or pd.Series)
    slope_long: Optional[Any] = None
    threshold_long: Optional[Any] = None
    slope_short: Optional[Any] = None
    threshold_short: Optional[Any] = None
