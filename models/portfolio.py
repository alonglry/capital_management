"""
Position and Portfolio data models.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Position:
    """
    Represents an open position in the portfolio.

    Required Fields:
        symbol (str): Ticker or currency pair symbol (e.g. 'AAPL', 'EURUSD').
        asset_class (str): Asset class ('equity', 'forex', 'crypto', etc.).
        side (str): Direction ('long' or 'short').
        quantity (float): Position size in shares, contracts, or units/lots.
        entry_price (float): Average entry price per unit.
        current_price (float): Current market price.
        stop_price (float): Current stop loss price level.
        monetary_risk_at_stop (float): Total monetary loss if stop loss is triggered.
        strategy_id (str): Strategy name or ID that owns this position.

    Optional Fields:
        sector (Optional[str]): Equity sector classification (e.g. 'Technology').
        country (Optional[str]): Country of issue or primary exposure (e.g. 'US').
        currency_exposure (Optional[Dict[str, float]]): Currency factor exposure dict (e.g. {'EUR': 1.0, 'USD': -1.0}).
        beta (Optional[float]): Market beta relative to benchmark.
        volatility (Optional[float]): Annualized volatility estimate.
        atr (Optional[float]): Current Average True Range value.
        pip_value (Optional[float]): Pip value per lot/unit for Forex instruments.
        point_value (Optional[float]): Point monetary value per contract for futures/FX.
    """
    symbol: str
    asset_class: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    stop_price: float
    monetary_risk_at_stop: float
    strategy_id: str

    sector: Optional[str] = None
    country: Optional[str] = None
    currency_exposure: Optional[Dict[str, float]] = None
    beta: Optional[float] = None
    volatility: Optional[float] = None
    atr: Optional[float] = None
    pip_value: Optional[float] = None
    point_value: Optional[float] = None


@dataclass
class PortfolioState:
    """
    Container for active portfolio positions and summary metrics.
    """
    positions: List[Position] = field(default_factory=list)

    def total_monetary_risk(self) -> float:
        """
        Calculates total monetary risk across all open positions.
        """
        return sum(pos.monetary_risk_at_stop for pos in self.positions)
