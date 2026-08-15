"""
Trade candidate data model and canonical stop-resolution helpers.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class TradeCandidate:
    """
    Represents an already-generated candidate trade proposed for capital allocation.

    Required Fields:
        symbol (str): Target symbol or pair (e.g. 'AAPL', 'EURUSD').
        asset_class (str): Asset class ('equity', 'forex', 'crypto', etc.).
        side (str): Direction ('long' or 'short').
        entry_price (float): Proposed entry price.

    Optional Fields:
        proposed_stop_price (Optional[float]): Strategy-supplied stop loss price level (default None).
        strategy_id (Optional[str]): Strategy identifier proposing this trade (default 'default').
        stop_price_source (Optional[str]): Source of the stop price ('strategy', 'atr', 'default').
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
        pip_value_currency (Optional[str]): Currency in which pip_value_per_lot is quoted.
        lot_size (Optional[float]): Base units per lot (default 100,000 for standard FX lot).
        point_value (Optional[float]): Monetary value per point move per unit/contract.
    """
    symbol: str
    asset_class: str
    side: str
    entry_price: float

    proposed_stop_price: Optional[float] = None
    strategy_id: Optional[str] = "default"
    stop_price_source: Optional[str] = None

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
    pip_value_currency: Optional[str] = None
    lot_size: Optional[float] = None
    point_value: Optional[float] = None

    # Conviction Parameters (supports scalar float or pd.Series)
    slope_long: Optional[Any] = None
    threshold_long: Optional[Any] = None
    slope_short: Optional[Any] = None
    threshold_short: Optional[Any] = None

    def validate_stop_direction(self, stop_price: Optional[float] = None) -> Tuple[bool, str]:
        """
        Validates stop loss price direction relative to entry price.

        LONG: stop_price < entry_price
        SHORT: stop_price > entry_price
        """
        target_stop = stop_price if stop_price is not None else self.proposed_stop_price
        if target_stop is None:
            return False, "Stop price is missing (None)."

        side_clean = self.side.lower()
        if side_clean == "long":
            if target_stop >= self.entry_price:
                return False, f"LONG stop price ({target_stop}) must be less than entry price ({self.entry_price})"
        elif side_clean == "short":
            if target_stop <= self.entry_price:
                return False, f"SHORT stop price ({target_stop}) must be greater than entry price ({self.entry_price})"
        else:
            return False, f"Invalid trade side '{self.side}'. Must be 'long' or 'short'."

        return True, "Valid stop direction"


def resolve_effective_stop_price(
    candidate: TradeCandidate,
    atr: Optional[float] = None,
    config: Optional[Any] = None,
) -> Tuple[float, str, float]:
    """
    Canonical single source of truth for resolving the effective stop price for a trade candidate.

    Precedence:
        1. Strategy Stop: If candidate.proposed_stop_price is provided, use it. Source = 'strategy'.
        2. Default ATR Stop: If candidate.proposed_stop_price is None and config.default_stop_method == 'atr',
           calculate effective_stop_price = entry_price - (atr * multiplier) [LONG]
                                           = entry_price + (atr * multiplier) [SHORT]
           Source = 'atr'.
        3. Unsupported / Reject: Otherwise raise ValueError.

    Validations:
        - Required inputs must be > 0 and finite (entry_price, atr, multiplier).
        - effective_stop_price > 0 and finite.
        - Direction check (LONG: stop < entry; SHORT: stop > entry).
        - stop_distance > 0.

    Args:
        candidate (TradeCandidate): Candidate trade object.
        atr (Optional[float]): Explicit ATR value (falls back to candidate.atr if None).
        config (Optional[Any]): CapitalManagementConfig instance.

    Returns:
        Tuple[float, str, float]: (effective_stop_price, stop_price_source, stop_distance)

    Raises:
        ValueError: If input validation fails or stop price cannot be resolved/validated.
    """
    entry = candidate.entry_price
    if entry <= 0 or not math.isfinite(entry):
        raise ValueError(f"Trade candidate entry_price ({entry}) must be > 0 and finite.")

    side_clean = candidate.side.lower()
    if side_clean not in ("long", "short"):
        raise ValueError(f"Invalid trade side '{candidate.side}'. Must be 'long' or 'short'.")

    # 1. Strategy Stop Precedence
    if candidate.proposed_stop_price is not None:
        proposed_stop = float(candidate.proposed_stop_price)
        if not math.isfinite(proposed_stop) or proposed_stop <= 0:
            raise ValueError(f"Proposed stop price ({proposed_stop}) must be > 0 and finite.")

        if side_clean == "long" and proposed_stop >= entry:
            raise ValueError(f"LONG proposed stop price ({proposed_stop}) must be less than entry price ({entry}).")
        if side_clean == "short" and proposed_stop <= entry:
            raise ValueError(f"SHORT proposed stop price ({proposed_stop}) must be greater than entry price ({entry}).")

        effective_stop = proposed_stop
        source = "strategy"

    # 2. Default Stop Fallback
    else:
        method = (getattr(config, "default_stop_method", "atr") or "atr").lower()
        if method == "atr":
            effective_atr = atr if atr is not None else candidate.atr
            if effective_atr is None or not math.isfinite(effective_atr) or effective_atr <= 0:
                raise ValueError(f"ATR is required, must be > 0 and finite for default ATR stop calculation (got {effective_atr}).")

            multiplier = float(getattr(config, "default_stop_atr_multiplier", 1.5))
            if not math.isfinite(multiplier) or multiplier <= 0:
                raise ValueError(f"default_stop_atr_multiplier ({multiplier}) must be > 0 and finite.")

            stop_dist_calc = effective_atr * multiplier

            if side_clean == "long":
                effective_stop = entry - stop_dist_calc
            else:  # short
                effective_stop = entry + stop_dist_calc

            source = "atr"
        else:
            raise ValueError(f"proposed_stop_price is None and unhandled or disabled default stop method '{method}'.")

    # 3. Final Validation of Effective Stop
    if not math.isfinite(effective_stop) or effective_stop <= 0:
        raise ValueError(f"Calculated effective_stop_price ({effective_stop}) must be > 0 and finite.")

    if side_clean == "long":
        if effective_stop >= entry:
            raise ValueError(f"LONG effective stop price ({effective_stop}) must be less than entry price ({entry}).")
        stop_distance = entry - effective_stop
    else:  # short
        if effective_stop <= entry:
            raise ValueError(f"SHORT effective stop price ({effective_stop}) must be greater than entry price ({entry}).")
        stop_distance = effective_stop - entry

    if stop_distance <= 0 or not math.isfinite(stop_distance):
        raise ValueError(f"Derived stop_distance ({stop_distance}) must be > 0 and finite.")

    return effective_stop, source, stop_distance
