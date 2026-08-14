"""
Market data container model.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MarketData:
    """
    Container for external market data consumed by risk modules.

    Fields:
        atr (Optional[Dict[str, float]]): Current ATR indexed by symbol.
        reference_atr (Optional[Dict[str, float]]): Reference/baseline ATR indexed by symbol.
        historical_volatility (Optional[Dict[str, float]]): Volatility metrics indexed by symbol.
        returns (Optional[Dict[str, List[float]]]): Historical return series indexed by symbol.
        correlation_matrix (Optional[Dict[str, Dict[str, float]]]): Asset correlation matrix mapped as dict[sym1][sym2] -> float.
        currency_exposure_matrix (Optional[Dict[str, Dict[str, float]]]): Default currency exposure factor breakdown per symbol.
        fx_rates (Optional[Dict[str, float]]): FX rates indexed by currency pair (e.g. {'GBPUSD': 1.28, 'EURUSD': 1.09}).
        as_of_timestamp (Optional[str]): ISO timestamp of market data.
        max_market_data_age (Optional[float]): Maximum allowed data age in seconds.
    """
    atr: Optional[Dict[str, float]] = field(default_factory=dict)
    reference_atr: Optional[Dict[str, float]] = field(default_factory=dict)
    historical_volatility: Optional[Dict[str, float]] = field(default_factory=dict)
    returns: Optional[Dict[str, List[float]]] = field(default_factory=dict)
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    currency_exposure_matrix: Optional[Dict[str, Dict[str, float]]] = field(default_factory=dict)
    fx_rates: Optional[Dict[str, float]] = field(default_factory=dict)
    as_of_timestamp: Optional[str] = None
    max_market_data_age: Optional[float] = None
