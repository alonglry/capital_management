"""
Legacy Merton Dynamic Risk & Lot Conversion Utilities.

DEPRECATION NOTICE:
    `calculate_merton_dynamic_risk()` is DEPRECATED in favor of `ConvictionRiskAllocatorModule`
    in the new modular pipeline (`capital_management.modules.ConvictionRiskAllocatorModule`).

Mathematical Differences:
    1. Legacy Merton combined long and short signals additively (long_conviction + short_conviction),
       which allowed conflicting long and short signals to cancel out or falsely amplify.
       The new `ConvictionRiskAllocatorModule` evaluates directional net conviction
       (net_conviction = long_conviction - short_conviction) and explicitly penalizes signal conflict
       (signal_conflict = min(long_conviction, short_conviction)).
    2. Legacy Merton directly mapped signal scalars to a hardcoded 0.5% - 4.5% risk fraction.
       `ConvictionRiskAllocatorModule` scales dynamically relative to `base_risk_budget`
       and supports pluggable linear / power mapping functions (`ConvictionMapping`).
    3. Legacy Merton produced a final risk capital allocation directly.
       `ConvictionRiskAllocatorModule` produces a REQUESTED risk budget, leaving portfolio-level
       hard constraints (heat, correlation, factor limits) to downstream risk modules.
"""

import warnings
from typing import Union

import numpy as np
import pandas as pd


def calculate_merton_dynamic_risk(
    slope_long: Union[float, pd.Series],
    threshold_long: Union[float, pd.Series],
    slope_short: Union[float, pd.Series],
    threshold_short: Union[float, pd.Series],
    account_capital: Union[float, pd.Series],
) -> Union[float, pd.Series]:
    """
    [DEPRECATED] Calculates dynamic risk capital allocation based on legacy Merton fractional Kelly dynamics.

    Use `ConvictionRiskAllocatorModule` for new strategy development.
    """
    warnings.warn(
        "calculate_merton_dynamic_risk() is deprecated. Use ConvictionRiskAllocatorModule instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    f_min = 0.005  # 0.5% risk for marginal threshold breaches
    f_max = 0.045  # 4.5% risk cap for extreme macro trends

    # LONG MATH
    max_conviction_long = threshold_long * 1.5
    denom_l = max_conviction_long - threshold_long
    if isinstance(denom_l, pd.Series):
        denom_l = denom_l.replace(0, np.nan)
    else:
        denom_l = denom_l if denom_l != 0 else np.nan

    raw_scalar_long = (slope_long - threshold_long) / denom_l

    # SHORT MATH
    max_conviction_short = threshold_short * 1.5
    denom_s = max_conviction_short - threshold_short
    if isinstance(denom_s, pd.Series):
        denom_s = denom_s.replace(0, np.nan)
    else:
        denom_s = denom_s if denom_s != 0 else np.nan

    raw_scalar_short = (slope_short - threshold_short) / denom_s

    # MERGE & CLIP DYNAMICS
    if isinstance(raw_scalar_long, pd.Series) or isinstance(raw_scalar_short, pd.Series):
        rl = pd.Series(raw_scalar_long) if not isinstance(raw_scalar_long, pd.Series) else raw_scalar_long
        rs = pd.Series(raw_scalar_short) if not isinstance(raw_scalar_short, pd.Series) else raw_scalar_short

        raw_scalar_combined = rl.add(rs, fill_value=0)
        signal_scalar = raw_scalar_combined.clip(lower=0.0, upper=1.0)
    else:
        val_l = raw_scalar_long if pd.notna(raw_scalar_long) else 0.0
        val_s = raw_scalar_short if pd.notna(raw_scalar_short) else 0.0
        raw_scalar_combined = val_l + val_s
        signal_scalar = max(0.0, min(1.0, raw_scalar_combined))

    # Calculate dynamic fraction
    dynamic_f = f_min + (f_max - f_min) * signal_scalar

    # Produce final allocatable capital threshold
    dynamic_risk_capital = account_capital * dynamic_f
    return dynamic_risk_capital


def convert_capital_to_mt4_lots(
    dynamic_risk_capital: float,
    current_volatility: float,
    symbol: str,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
    lot_step: float = 0.01,
) -> float:
    """
    Converts raw risk capital into MT4 executable standard lots based on structural volatility constraints.
    Applies rigorous Broker Lot Normalization to prevent MT4 "Invalid Volume" rejections.
    """
    frictional_pip = 0.15 if symbol.endswith("JPY") else 0.0015
    safe_vol = max(current_volatility, frictional_pip * 3)

    raw_lots = (dynamic_risk_capital / safe_vol) / 100000.0
    stepped_lots = np.floor(raw_lots / lot_step) * lot_step

    return float(np.clip(stepped_lots, min_lot, max_lot))