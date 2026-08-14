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
    """
    atr: Optional[Dict[str, float]] = field(default_factory=dict)
    reference_atr: Optional[Dict[str, float]] = field(default_factory=dict)
    historical_volatility: Optional[Dict[str, float]] = field(default_factory=dict)
    returns: Optional[Dict[str, List[float]]] = field(default_factory=dict)
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    currency_exposure_matrix: Optional[Dict[str, Dict[str, float]]] = field(default_factory=dict)
