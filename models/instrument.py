"""
Instrument Specification Data Model.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class InstrumentSpec:
    """
    Metadata specification defining instrument mechanics, sizing steps, and pip/point valuations.

    Args:
        symbol (str): Instrument symbol (e.g. 'AAPL', 'EURUSD').
        asset_class (str): Asset class ('EQUITY', 'FOREX', 'CRYPTO', 'FUTURE', 'ETF', 'CFD').
        contract_size (float): Contract size multiplier (e.g. 100,000 for standard FX lot, 1.0 for equity).
        price_increment (float): Minimum price tick increment (e.g. 0.01 for equity, 0.00001 for 5-digit FX).
        pip_size (float): Pip unit size (e.g. 0.0001 for EURUSD, 0.01 for USDJPY, 1.0 for equity).
        quantity_increment (float): Minimum quantity lot/share step (e.g. 1.0 for equity shares, 0.01 for FX lots).
        min_quantity (float): Minimum tradeable size.
        max_quantity (float): Maximum tradeable size.
        point_value (float): Monetary value per price point move per contract/share.
        quote_currency (str): Quote currency (e.g. 'USD').
        base_currency (str): Base currency (e.g. 'EUR').
        settlement_currency (str): Account settlement currency (e.g. 'USD').
    """
    symbol: str
    asset_class: str
    contract_size: float = 1.0
    price_increment: float = 0.01
    pip_size: float = 0.0001
    quantity_increment: float = 1.0
    min_quantity: float = 1.0
    max_quantity: float = 100000.0
    point_value: float = 1.0
    quote_currency: str = "USD"
    base_currency: str = "USD"
    settlement_currency: str = "USD"

    @classmethod
    def create_default(cls, symbol: str, asset_class: str) -> "InstrumentSpec":
        """
        Creates a default InstrumentSpec based on asset class.
        """
        ac = asset_class.upper()
        if ac == "FOREX":
            is_jpy = "JPY" in symbol.upper()
            pip_size = 0.01 if is_jpy else 0.0001
            price_inc = 0.001 if is_jpy else 0.00001
            base_ccy = symbol[:3].upper() if len(symbol) >= 6 else "EUR"
            quote_ccy = symbol[3:6].upper() if len(symbol) >= 6 else "USD"
            return cls(
                symbol=symbol,
                asset_class="FOREX",
                contract_size=100000.0,
                price_increment=price_inc,
                pip_size=pip_size,
                quantity_increment=0.01,
                min_quantity=0.01,
                max_quantity=100.0,
                point_value=1.0,
                base_currency=base_ccy,
                quote_currency=quote_ccy,
                settlement_currency="USD",
            )
        else:
            return cls(
                symbol=symbol,
                asset_class="EQUITY",
                contract_size=1.0,
                price_increment=0.01,
                pip_size=1.0,
                quantity_increment=1.0,
                min_quantity=1.0,
                max_quantity=100000.0,
                point_value=1.0,
                base_currency="USD",
                quote_currency="USD",
                settlement_currency="USD",
            )

    def calculate_monetary_risk_per_unit(self, entry_price: float, stop_price: float, pip_value_per_lot: Optional[float] = None) -> float:
        """
        Calculates the monetary risk per 1.0 unit (1 share or 1 lot) given entry and stop prices.

        Formula:
            Forex (with pip_value_per_lot): (stop_distance / pip_size) * pip_value_per_lot
            Generic: stop_distance * point_value * contract_size
        """
        stop_dist = abs(entry_price - stop_price)
        ac = self.asset_class.upper()

        if ac == "FOREX" and pip_value_per_lot is not None and pip_value_per_lot > 0:
            pips = stop_dist / self.pip_size if self.pip_size > 0 else 0.0
            return pips * pip_value_per_lot
        else:
            return stop_dist * self.point_value * self.contract_size
