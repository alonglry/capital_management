"""
Instrument Specification Data Model & FX Conversion Layer.
"""

from dataclasses import dataclass, field
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
        Derived: monetary_risk_per_unit, loss_for_price_move.
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
    metadata_verified: bool = True
    metadata_source: str = "explicit"

    @property
    def instrument_metadata_source(self) -> str:
        """Alias for metadata_source for backward compatibility."""
        return self.metadata_source

    @instrument_metadata_source.setter
    def instrument_metadata_source(self, val: str) -> None:
        self.metadata_source = val

    @classmethod
    def create_default(cls, symbol: str, asset_class: str) -> "InstrumentSpec":
        """
        Creates a fallback default InstrumentSpec based on asset class.
        Marked metadata_verified = False, metadata_source = 'legacy_default'.
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
                metadata_verified=False,
                metadata_source="legacy_default",
            )

    def validate_broker_rules(self) -> Tuple[bool, str]:
        """
        Validates consistency of broker quantity rules.
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

    def get_fx_conversion(
        self,
        source_currency: str,
        target_currency: str = "USD",
        entry_price: float = 1.0,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> Optional[FXConversionResult]:
        """
        Returns auditable FXConversionResult for converting source_currency to target_currency.
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

        base_ccy = self.base_currency.upper()
        quote_ccy = self.quote_currency.upper()

        if src == quote_ccy and base_ccy == tgt and entry_price > 0:
            return FXConversionResult(
                source_currency=src,
                target_currency=tgt,
                conversion_rate=1.0 / entry_price,
                rate_source="entry_price_inversion",
                direct_or_inverse="inverse",
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

        return None

    def get_fx_conversion_rate(
        self,
        account_currency: str = "USD",
        entry_price: float = 1.0,
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> Optional[float]:
        res = self.get_fx_conversion(self.quote_currency, account_currency, entry_price, fx_rates)
        return res.conversion_rate if res else None

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
        Prevents double-counting contract_size when pip_value_per_lot is supplied.
        """
        dist = abs(price_move_distance)
        ac = self.asset_class.upper()

        if ac == "FOREX" and pip_value_per_lot is not None and pip_value_per_lot > 0:
            pips = dist / self.pip_size if self.pip_size > 0 else 0.0
            pip_ccy = (pip_value_currency or account_currency).upper()
            conv = self.get_fx_conversion(pip_ccy, account_currency, entry_price, fx_rates)
            if conv is None:
                raise ValueError(f"Missing required FX conversion rate from {pip_ccy} to {account_currency}")
            pip_val_acct = pip_value_per_lot * conv.conversion_rate
            return pips * pip_val_acct * quantity
        else:
            native_loss_per_unit = dist * self.point_value * self.contract_size
            conv = self.get_fx_conversion(self.quote_currency, account_currency, entry_price, fx_rates)
            if conv is None and self.quote_currency.upper() != account_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {self.quote_currency} to {account_currency}")
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
