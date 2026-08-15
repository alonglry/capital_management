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

    def __post_init__(self):
        ac = (self.asset_class or "").upper()
        if not self.valuation_method:
            self.valuation_method = "pip_value_per_lot" if ac == "FOREX" else "contract_point_value"
        if self.min_quantity is None:
            self.min_quantity = 0.01 if ac == "FOREX" else 1.0
        if self.max_quantity is None:
            self.max_quantity = 100.0 if ac == "FOREX" else 100000.0
        if self.quantity_increment is None:
            self.quantity_increment = 0.01 if ac == "FOREX" else 1.0
        if ac == "EQUITY":
            if self.point_value is None:
                self.point_value = 1.0
            if self.contract_size is None:
                self.contract_size = 1.0
            if not self.quote_currency:
                self.quote_currency = "USD"
            if not self.base_currency:
                self.base_currency = "USD"

    @property
    def instrument_metadata_source(self) -> str:
        return self.metadata_source or ""

    @instrument_metadata_source.setter
    def instrument_metadata_source(self, val: str) -> None:
        self.metadata_source = val

    @classmethod
    def create_default(cls, symbol: str, asset_class: str) -> "InstrumentSpec":
        """
        Explicit utility creating a default InstrumentSpec based on asset class.
        Marked metadata_verified = False, metadata_source = 'legacy_default'.
        Note: Production capital management pipeline unconditionally rejects metadata_verified = False.
        """
        ac = asset_class.upper()
        if ac == "FOREX":
            clean_symbol = symbol.upper().replace("=X", "").strip()
            if len(clean_symbol) < 6:
                raise ValueError(f"Invalid Forex symbol '{symbol}'. Must be at least 6 characters (e.g. 'EURUSD' or 'EURUSD=X').")
            base_ccy = clean_symbol[:3]
            quote_ccy = clean_symbol[3:6]
            is_jpy = "JPY" in clean_symbol
            pip_size = 0.01 if is_jpy else 0.0001
            price_inc = 0.001 if is_jpy else 0.00001
            return cls(
                symbol=symbol,
                asset_class="FOREX",
                contract_size=100000.0,      #1 standard lot
                price_increment=price_inc,
                pip_size=pip_size,
                quantity_increment=0.01,     #1 microlot
                min_quantity=0.01,           #1 microlot
                max_quantity=100.0,          #100 standard lots
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
                contract_size=1.0,          #1 share
                price_increment=0.01,       #0.01 dollar per share
                pip_size=1.0,               #1 dollar per share
                quantity_increment=1.0,     #1 share
                min_quantity=1.0,           #1 share
                max_quantity=100000.0,      #100,000 shares
                point_value=1.0,            #1 dollar per share
                base_currency="USD",
                quote_currency="USD",
                settlement_currency="USD",
                valuation_method="contract_point_value",
                metadata_verified=False,
                metadata_source="legacy_default",
            )

    def validate_for_capital_management(self, account_currency: str, trade: any) -> Tuple[bool, str]:
        """
        Unconditionally validates completeness and correctness of InstrumentSpec metadata for production capital management.
        """
        if not self.metadata_verified:
            return False, "InstrumentSpec metadata_verified is False."
        if not self.metadata_source or not self.metadata_source.strip():
            return False, "InstrumentSpec metadata_source is empty or None."

        if self.min_quantity is None or self.min_quantity <= 0:
            return False, f"Invalid min_quantity ({self.min_quantity})"
        if self.max_quantity is None or self.max_quantity < self.min_quantity:
            return False, f"Invalid max_quantity ({self.max_quantity}) relative to min_quantity ({self.min_quantity})"
        if self.quantity_increment is None or self.quantity_increment <= 0:
            return False, f"Invalid quantity_increment ({self.quantity_increment})"

        ac = self.asset_class.upper()
        v_method = (self.valuation_method or "").lower()

        if ac == "FOREX":
            if not self.base_currency or not self.quote_currency:
                return False, "Forex instrument requires base_currency and quote_currency."

        if not v_method or v_method not in ("pip_value_per_lot", "contract_point_value"):
            return False, f"Unsupported or missing valuation_method ('{self.valuation_method}'). Must be 'pip_value_per_lot' or 'contract_point_value'."

        if v_method == "pip_value_per_lot":
            if ac != "FOREX":
                return False, f"valuation_method 'pip_value_per_lot' is only valid for FOREX asset_class (got {self.asset_class})."
            if self.pip_size is None or self.pip_size <= 0:
                return False, f"valuation_method 'pip_value_per_lot' requires pip_size > 0 (got {self.pip_size})."
            if trade.pip_value_per_lot is None or trade.pip_value_per_lot <= 0:
                return False, f"valuation_method 'pip_value_per_lot' requires trade.pip_value_per_lot > 0 (got {trade.pip_value_per_lot})."
            if not trade.pip_value_currency:
                return False, "valuation_method 'pip_value_per_lot' requires explicit trade.pip_value_currency (cannot be None)."
        elif v_method == "contract_point_value":
            if self.contract_size is None or self.contract_size <= 0:
                return False, f"valuation_method 'contract_point_value' requires contract_size > 0 (got {self.contract_size})."
            if self.point_value is None or self.point_value <= 0:
                return False, f"valuation_method 'contract_point_value' requires point_value > 0 (got {self.point_value})."
            if not self.quote_currency:
                return False, "valuation_method 'contract_point_value' requires quote_currency."

        return True, "Valid InstrumentSpec for production capital management"

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

    def calculate_notional_value(
        self,
        quantity: float,
        entry_price: float,
        target_currency: str = "USD",
        fx_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculates canonical total notional value of position expressed in target_currency.

        Forex Semantics:
            quantity represents LOTS. base_notional = quantity * contract_size.
            notional_target = base_notional * FX(base_currency -> target_currency).
            (Does NOT use entry_price when converting base notional).

        Equity Semantics:
            quantity represents SHARES. quote_notional = quantity * entry_price * point_value.
            notional_target = quote_notional * FX(quote_currency -> target_currency).
        """
        ac = self.asset_class.upper()
        if ac == "FOREX":
            if self.contract_size is None or self.contract_size <= 0:
                raise ValueError(f"Invalid contract_size ({self.contract_size}) for Forex notional calculation.")
            base_ccy = self.base_currency or "EUR"
            base_notional = quantity * self.contract_size
            conv = self.get_fx_conversion(base_ccy, target_currency, entry_price, fx_rates)
            if conv is None and base_ccy.upper() != target_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {base_ccy} to {target_currency}")
            rate = conv.conversion_rate if conv else 1.0
            return base_notional * rate
        else:
            pt_val = self.point_value if self.point_value is not None else 1.0
            quote_ccy = self.quote_currency or "USD"
            quote_notional = quantity * entry_price * pt_val
            conv = self.get_fx_conversion(quote_ccy, target_currency, entry_price, fx_rates)
            if conv is None and quote_ccy.upper() != target_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {quote_ccy} to {target_currency}")
            rate = conv.conversion_rate if conv else 1.0
            return quote_notional * rate

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
        Canonical monetary loss function for a given price move distance and executable quantity
        strictly adhering to valuation_method.
        """
        dist = abs(price_move_distance)
        v_method = (self.valuation_method or "").lower()

        if v_method == "pip_value_per_lot":
            if self.pip_size is None or self.pip_size <= 0:
                raise ValueError(f"Invalid pip_size ({self.pip_size}) for pip_value_per_lot valuation.")
            if pip_value_per_lot is None or pip_value_per_lot <= 0:
                raise ValueError(f"Invalid pip_value_per_lot ({pip_value_per_lot}) for pip_value_per_lot valuation.")

            pip_ccy = (pip_value_currency or account_currency).upper()
            pips = dist / self.pip_size
            conv = self.get_fx_conversion(pip_ccy, account_currency, entry_price, fx_rates)
            if conv is None:
                raise ValueError(f"Missing required FX conversion rate from {pip_ccy} to {account_currency}")
            pip_val_acct = pip_value_per_lot * conv.conversion_rate
            return pips * pip_val_acct * quantity

        elif v_method == "contract_point_value":
            contract = self.contract_size if self.contract_size is not None else 1.0
            pt_val = self.point_value if self.point_value is not None else 1.0
            native_loss_per_unit = dist * pt_val * contract

            quote_ccy = (self.quote_currency or "USD").upper()
            conv = self.get_fx_conversion(quote_ccy, account_currency, entry_price, fx_rates)
            if conv is None and quote_ccy != account_currency.upper():
                raise ValueError(f"Missing required FX conversion rate from {quote_ccy} to {account_currency}")
            rate = conv.conversion_rate if conv else 1.0
            return native_loss_per_unit * rate * quantity
        else:
            raise ValueError(f"Unsupported valuation_method '{self.valuation_method}' in calculate_loss_for_price_move.")

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
