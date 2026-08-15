"""
Account state data model.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AccountState:
    """
    Represents the trading account's equity, cash balance, base currency, and historical peak equity.

    Args:
        equity (float): Current account equity.
        cash (float): Free cash available in account currency.
        currency (str): Account base currency (e.g. 'USD').
        peak_equity (Optional[float]): High-water mark equity for drawdown calculations.
    """
    equity: float
    cash: float
    currency: str = "USD"
    peak_equity: Optional[float] = None
    is_initialized: bool = True

    def get_peak_equity(self) -> float:
        """
        Returns the effective peak equity, defaulting to current equity if unassigned or lower.
        """
        if self.peak_equity is not None and self.peak_equity > 0:
            return max(self.peak_equity, self.equity)
        return self.equity
