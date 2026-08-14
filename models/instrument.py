"""
Instrument Specification Data Model.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


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
        point_value (float): Monetary value per price point move per contract/share in native quote currency.
        quote_currency (str): Quote currency (e.g. 'USD').
        base_currency (str): Base currency (e.g. 'EUR').
        settlement_currency (str): Account settlement currency (e.g. 'USD').
        instrument_metadata_source (str): Source of metadata ('explicit', 'broker', 'exchange', 'market_data', 'legacy_default').
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
    instrument_metadata_source: str = "explicit"

    @classmethod
    def create_default(cls, symbol: str, asset_class: str) -> "InstrumentSpec":
        """
        Creates a fallback default InstrumentSpec based on asset class.
        Marked with instrument_metadata_source = 'legacy_default'.
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
                instrument_metadata_source="legacy_default",
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
                instrument_metadata_source="legacy_default",
            )

    def validate_broker_rules(self) -> Tuple[bool, str]:
        """
        Validates consistency of broker quantity rules.

        Returns:
            Tuple[bool, str]: (is_valid, error_reason)
        """
        if self.min_quantity <= 0:
            return False, f"min_quantity ({self.min_quantity}) must be > 0"
        if self.max_quantity < self.min_quantity:
            return False, f"min_quantity ({self.min_quantity}) exceeds max_quantity ({self.max_quantity})"
        if self.quantity_increment <= 0:
            return False, f"quantity_increment ({self.quantity_increment}) must be > 0"

        # Check alignment of min_quantity with quantity_increment
        min_rem = abs(self.min_quantity / self.quantity_increment - round(self.min_quantity / self.quantity_increment))
        if min_rem > 1e-4:
            return False, f"min_quantity ({self.min_quantity}) is not aligned with quantity_increment ({self.quantity_increment})"

        # Check alignment of max_quantity with quantity_increment
        max_rem = abs(self.max_quantity / self.quantity_increment - round(self.max_quantity / self.quantity_increment))
        if max_rem > 1e-4:
            return False, f"max_quantity ({self.max_quantity}) is not aligned with quantity_increment ({self.quantity_increment})"

        return True, "Valid broker quantity rules"

    def get_fx_conversion_rate(
        self,
        account_currency: str = "USD",
        entry_price: float = 1.0,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> Optional[float]:
        """
        Computes FX conversion rate from instrument quote currency to account currency.

        Args:
            account_currency (str): Account base currency (e.g. 'USD', 'EUR').
            entry_price (float): Entry price of base/quote pair.
            fx_rates (Optional[Dict[str, float]]): Market FX rates dictionary (e.g. {'GBPUSD': 1.28}).

        Returns:
            Optional[float]: Rate multiplier to convert quote currency to account currency, or None if unavailable.
        """
        quote_ccy = self.quote_currency.upper()
        base_ccy = self.base_currency.upper()
        acct_ccy = account_currency.upper()

        if quote_ccy == acct_ccy:
            return 1.0

        if base_ccy == acct_ccy and entry_price > 0:
            return 1.0 / entry_price

        if fx_rates:
            # Check direct pair QUOTE/ACCT e.g. GBPUSD for GBP quote and USD account
            direct_pair = f"{quote_ccy}{acct_ccy}"
            if direct_pair in fx_rates and fx_rates[direct_pair] > 0:
                return float(fx_rates[direct_pair])

            # Check inverse pair ACCT/QUOTE e.g. USDGBP
            inverse_pair = f"{acct_ccy}{quote_ccy}"
            if inverse_pair in fx_rates and fx_rates[inverse_pair] > 0:
                return 1.0 / float(fx_rates[inverse_pair])

        return None

    def calculate_monetary_risk_per_unit(
        self,
        entry_price: float,
        stop_price: float,
        pip_value_per_lot: Optional[float] = None,
        account_currency: str = "USD",
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculates the monetary risk per 1.0 unit (1 share or 1 lot) in account currency.

        Args:
            entry_price (float): Entry price.
            stop_price (float): Proposed stop loss price.
            pip_value_per_lot (Optional[float]): Monetary pip value for 1 lot in native or account currency.
            account_currency (str): Account settlement currency.
            fx_rates (Optional[Dict[str, float]]): FX rate lookup dict.

        Returns:
            float: Monetary risk per unit in account currency.
        """
        stop_dist = abs(entry_price - stop_price)
        ac = self.asset_class.upper()

        if ac == "FOREX" and pip_value_per_lot is not None and pip_value_per_lot > 0:
            pips = stop_dist / self.pip_size if self.pip_size > 0 else 0.0
            return pips * pip_value_per_lot
        else:
            native_risk = stop_dist * self.point_value * self.contract_size
            rate = self.get_fx_conversion_rate(account_currency, entry_price, fx_rates)
            if rate is None and self.quote_currency.upper() != account_currency.upper():
                raise ValueError(
                    f"Missing required FX conversion rate from {self.quote_currency} to {account_currency}"
                )
            return native_risk * (rate if rate is not None else 1.0)

