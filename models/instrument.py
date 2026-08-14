"""
Instrument Specification Data Model & FX Conversion Layer.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class FXConversionResult:
    """
    Auditable result container for currency conversion rates.
    """
    source_currency: str
    target_currency: str
    conversion_rate: float
    rate_source: str
    rate_timestamp: Optional[str] = None
    direct_or_inverse: str = "direct"


@dataclass
class InstrumentSpec:
    """
    Metadata specification defining instrument mechanics, sizing steps, and pip/point valuations.

    Explicit Classification:
        Required: symbol, asset_class, min_quantity, max_quantity, quantity_increment, quote_currency, base_currency, settlement_currency.
        Optional: pip_size, pip_value_per_lot, pip_value_currency, point_value, contract_size, price_increment.
        Derived: monetary_risk_per_unit, loss_for_price_move, notional_value.
    """
    symbol: str
    asset_class: str
    contract_size: Optional[float] = None
    price_increment: Optional[float] = None
    pip_size: Optional[float] = None
    quantity_increment: Optional[float] = None
    min_quantity: Optional[float] = None
    max_quantity: Optional[float] = None
    point_value: Optional[float] = None
    quote_currency: Optional[str] = None
    base_currency: Optional[str] = None
    settlement_currency: Optional[str] = None
    valuation_method: Optional[str] = None  # 'pip_value_per_lot' or 'contract_point_value'
    metadata_verified: bool = False
    metadata_source: Optional[str] = None

    @property
    def instrument_metadata_source(self) -> str:
        """Alias for metadata_source for backward compatibility."""
        return self.metadata_source or "unspecified"

    @instrument_metadata_source.setter
    def instrument_metadata_source(self, val: str) -> None:
        self.metadata_source = val

    @classmethod
    def create_default(cls, symbol: str, asset_class: str) -> "InstrumentSpec":
        """
        Explicit utility creating a default InstrumentSpec based on asset class.
        Marked metadata_verified = False, metadata_source = 'legacy_default'.
        Note: The pipeline does not invoke this automatically in production mode.
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
                valuation_method="pip_value_per_lot",
                metadata_verified=False,
                metadata_source="legacy_default",
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
                valuation_method="contract_point_value",
                metadata_verified=False,
                metadata_source="legacy_default",
            )

    def validate_for_capital_management(self, account_currency: str, trade: any) -> Tuple[bool, str]:
        """
        Validates completeness and correctness of InstrumentSpec metadata for production capital management.
        """
        if not self.metadata_verified:
            return False, "InstrumentSpec metadata_verified is False."
        if not self.metadata_source:
            return False, "InstrumentSpec metadata_source is empty or None."

        if self.min_quantity is None or self.min_quantity <= 0:
            return False, f"Invalid min_quantity ({self.min_quantity})"
        if self.max_quantity is None or self.max_quantity < self.min_quantity:
            return False, f"Invalid max_quantity ({self.max_quantity}) relative to min_quantity ({self.min_quantity})"
        if self.quantity_increment is None or self.quantity_increment <= 0:
            return False, f"Invalid quantity_increment ({self.quantity_increment})"

        ac = self.asset_class.upper()
        if ac == "FOREX":
            if not self.base_currency or not self.quote_currency:
                return False, "Forex instrument requires base_currency and quote_currency."
            if self.pip_size is None or self.pip_size <= 0:
                return False, f"Forex instrument requires pip_size > 0 (got {self.pip_size})."
            if trade.pip_value_per_lot is None or trade.pip_value_per_lot <= 0:
                return False, f"Forex trade candidate requires pip_value_per_lot > 0 (got {trade.pip_value_per_lot})."
        else:
            if not self.quote_currency:
                return False, "Equity instrument requires quote_currency."
            if self.point_value is None or self.point_value <= 0:
                return False, f"Equity instrument requires point_value > 0 (got {self.point_value})."

        return True, "Valid InstrumentSpec for capital management"

    def validate_broker_rules(self) -> Tuple[bool, str]:
        """
        Validates quantity rules consistency.
        """
        if self.min_quantity is None or self.min_quantity <= 0:
            return False, f"min_quantity ({self.min_quantity}) must be > 0"
        if self.max_quantity is None or self.max_quantity < self.min_quantity:
            return False, f"min_quantity ({self.min_quantity}) exceeds max_quantity ({self.max_quantity})"
        if self.quantity_increment is None or self.quantity_increment <= 0:
            return False, f"quantity_increment ({self.quantity_increment}) must be > 0"
        return True, "Valid broker quantity rules"

    def get_fx_conversion(
        self,
        source_currency: str,
        target_currency: str = "USD",
        entry_price: float = 1.0,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> Optional[FXConversionResult]:
        """
        Returns auditable FXConversionResult for converting source_currency to target_currency.
        Priority:
        1. Market-data FX rates direct or inverse.
        2. Identity conversion (source == target).
        3. Instrument-derived entry price inversion (if quote -> base).
        """
        src = source_currency.upper()
        tgt = target_currency.upper()

        if src == tgt:
            return FXConversionResult(
                source_currency=src,
                target_currency=tgt,
                conversion_rate=1.0,
                rate_source="identity",
                direct_or_inverse="direct",
            )

        if fx_rates:
            direct_pair = f"{src}{tgt}"
            if direct_pair in fx_rates and fx_rates[direct_pair] > 0:
                return FXConversionResult(
                    source_currency=src,
                    target_currency=tgt,
                    conversion_rate=float(fx_rates[direct_pair]),
                    rate_source=f"market_data.{direct_pair}",
                    direct_or_inverse="direct",
                )

            inverse_pair = f"{tgt}{src}"
            if inverse_pair in fx_rates and fx_rates[inverse_pair] > 0:
                return FXConversionResult(
                    source_currency=src,
                    target_currency=tgt,
                    conversion_rate=1.0 / float(fx_rates[inverse_pair]),
                    rate_source=f"market_data.{inverse_pair}",
                    direct_or_inverse="inverse",
                )

        base_ccy = (self.base_currency or "USD").upper()
        quote_ccy = (self.quote_currency or "USD").upper()

        if src == quote_ccy and base_ccy == tgt and entry_price > 0:
            return FXConversionResult(
                source_currency=src,
                target_currency=tgt,
                conversion_rate=1.0 / entry_price,
                rate_source="entry_price_inversion",
                direct_or_inverse="inverse",
            )

        return None

    def get_fx_conversion_rate(
        self,
        account_currency: str = "USD",
        entry_price: float = 1.0,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> Optional[float]:
        res = self.get_fx_conversion(self.quote_currency or "USD", account_currency, entry_price, fx_rates)
        return res.conversion_rate if res else None

    def calculate_notional_value(
        self,
        quantity: float,
        entry_price: float,
        account_currency: str = "USD",
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculates canonical total notional value of position in account currency.
        """
        ac = self.asset_class.upper()
        if ac == "FOREX":
            contract = self.contract_size if self.contract_size is not None else 100000.0
            base_ccy = self.base_currency or "EUR"
            conv = self.get_fx_conversion(base_ccy, account_currency, entry_price, fx_rates)
            if conv is None and base_ccy.upper() != account_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {base_ccy} to {account_currency}")
            rate = conv.conversion_rate if conv else 1.0
            return quantity * contract * rate
        else:
            pt_val = self.point_value if self.point_value is not None else 1.0
            quote_ccy = self.quote_currency or "USD"
            conv = self.get_fx_conversion(quote_ccy, account_currency, entry_price, fx_rates)
            if conv is None and quote_ccy.upper() != account_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {quote_ccy} to {account_currency}")
            rate = conv.conversion_rate if conv else 1.0
            return quantity * entry_price * pt_val * rate

    def calculate_loss_for_price_move(
        self,
        price_move_distance: float,
        quantity: float,
        account_currency: str = "USD",
        entry_price: float = 1.0,
        pip_value_per_lot: Optional[float] = None,
        pip_value_currency: Optional[str] = None,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Canonical monetary loss function for a given price move distance and executable quantity.
        """
        dist = abs(price_move_distance)
        ac = self.asset_class.upper()
        pip_sz = self.pip_size if self.pip_size is not None else 0.0001
        pt_val = self.point_value if self.point_value is not None else 1.0
        contract = self.contract_size if self.contract_size is not None else 1.0

        if ac == "FOREX" and pip_value_per_lot is not None and pip_value_per_lot > 0:
            pips = dist / pip_sz if pip_sz > 0 else 0.0
            pip_ccy = (pip_value_currency or account_currency).upper()
            conv = self.get_fx_conversion(pip_ccy, account_currency, entry_price, fx_rates)
            if conv is None:
                raise ValueError(f"Missing required FX conversion rate from {pip_ccy} to {account_currency}")
            pip_val_acct = pip_value_per_lot * conv.conversion_rate
            return pips * pip_val_acct * quantity
        else:
            native_loss_per_unit = dist * pt_val * contract
            quote_ccy = self.quote_currency or "USD"
            conv = self.get_fx_conversion(quote_ccy, account_currency, entry_price, fx_rates)
            if conv is None and quote_ccy.upper() != account_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {quote_ccy} to {account_currency}")
            rate = conv.conversion_rate if conv else 1.0
            return native_loss_per_unit * rate * quantity

    def calculate_monetary_risk_per_unit(
        self,
        entry_price: float,
        stop_price: float,
        pip_value_per_lot: Optional[float] = None,
        pip_value_currency: Optional[str] = None,
        account_currency: str = "USD",
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculates monetary risk per 1.0 executable unit (1 share or 1 lot) in account currency.
        """
        stop_dist = abs(entry_price - stop_price)
        return self.calculate_loss_for_price_move(
            price_move_distance=stop_dist,
            quantity=1.0,
            account_currency=account_currency,
            entry_price=entry_price,
            pip_value_per_lot=pip_value_per_lot,
            pip_value_currency=pip_value_currency,
            fx_rates=fx_rates,
        )
