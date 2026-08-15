"""
Configuration data models for Capital Management Engine.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DrawdownRule:
    """
    Tier rule for Drawdown Governor module.

    Args:
        min_dd (float): Minimum drawdown threshold (inclusive).
        max_dd (float): Maximum drawdown threshold (exclusive).
        multiplier (float): Risk budget multiplier (e.g. 0.75 for 25% reduction).
    """
    min_dd: float
    max_dd: float
    multiplier: float


@dataclass
class VolatilityRule:
    """
    Tier rule for Volatility Governor module based on ATR Ratio (Current ATR / Reference ATR).

    Args:
        min_ratio (float): Minimum ATR ratio threshold (inclusive).
        max_ratio (float): Maximum ATR ratio threshold (exclusive).
        multiplier (float): Risk budget multiplier.
    """
    min_ratio: float
    max_ratio: float
    multiplier: float


@dataclass
class ConvictionRiskConfig:
    """
    Configuration for Dynamic Conviction Risk Allocator module.

    Args:
        conviction_threshold_multiplier (float): Scalar multiplier for max conviction threshold (default 1.5).
        min_multiplier (float): Conviction multiplier minimum bound at 0 strength (default 0.50).
        max_multiplier (float): Conviction multiplier maximum bound at 1 strength (default 1.50).
        conflict_penalty (float): Penalty factor applied to signal conflict (default 0.50).
        mapping_type (str): Mapping function identifier ('linear' or 'power').
        power_gamma (float): Exponent for power mapping (default 1.0).
    """
    conviction_threshold_multiplier: float = 1.5
    min_multiplier: float = 0.50
    max_multiplier: float = 1.50
    conflict_penalty: float = 0.50
    mapping_type: str = "linear"
    power_gamma: float = 1.0

    def __post_init__(self):
        if self.min_multiplier < 0 or self.max_multiplier < self.min_multiplier:
            raise ValueError(f"Invalid conviction multipliers: min={self.min_multiplier}, max={self.max_multiplier}")


def default_drawdown_rules() -> List[DrawdownRule]:
    return [
        DrawdownRule(min_dd=0.00, max_dd=0.05, multiplier=1.00),
        DrawdownRule(min_dd=0.05, max_dd=0.10, multiplier=0.75),
        DrawdownRule(min_dd=0.10, max_dd=0.15, multiplier=0.50),
        DrawdownRule(min_dd=0.15, max_dd=0.20, multiplier=0.25),
        DrawdownRule(min_dd=0.20, max_dd=float("inf"), multiplier=0.00),
    ]


def default_volatility_rules() -> List[VolatilityRule]:
    return [
        VolatilityRule(min_ratio=0.00, max_ratio=0.70, multiplier=0.75),
        VolatilityRule(min_ratio=0.70, max_ratio=1.30, multiplier=1.00),
        VolatilityRule(min_ratio=1.30, max_ratio=1.80, multiplier=0.75),
        VolatilityRule(min_ratio=1.80, max_ratio=float("inf"), multiplier=0.50),
    ]


def default_modules_config() -> Dict[str, bool]:
    return {
        "base_risk": True,
        "conviction_allocator": True,
        "drawdown_governor": True,
        "volatility_governor": True,
        "strategy_allocation": True,
        "portfolio_heat": True,
        "correlation_risk": True,
        "correlation_check": True,
        "factor_exposure": True,
        "factor_check": True,
        "stop_risk": True,
        "position_sizing": True,
        "transaction_cost": True,
        "stress_test": True,
        "final_validation": True,
    }


def default_strategy_allocations() -> Dict[str, float]:
    return {
        "mean_reversion": 1.00,
        "momentum": 0.75,
        "breakout": 0.75,
        "carry": 0.50,
        "default": 1.00,
    }


def default_factor_limits() -> Dict[str, float]:
    return {
        "USD": 2.0,
        "EUR": 2.0,
        "GBP": 2.0,
        "JPY": 2.0,
        "AUD": 2.0,
        "CAD": 2.0,
        "CHF": 2.0,
        "NZD": 2.0,
        "market_beta": 1.5,
        "Technology": 0.30,
        "Financials": 0.30,
    }


def default_stress_limits() -> Dict[str, float]:
    return {
        "max_stress_risk_pct": 0.02,
        "gap_pct": 0.01,
        "extra_slippage_pct": 0.005,
    }


def default_transaction_costs() -> Dict[str, Any]:
    return {
        "default_spread": 0.0,
        "default_commission": 0.0,
        "default_slippage": 0.0,
        "commission_type": "per_unit",  # 'per_unit', 'fixed', 'percentage'
        "commission_rate_basis": 0.001,  # 0.001 = 10 bps
        "commission_currency": "account",
        "spread_unit": "price",  # 'price', 'pips', 'percentage'
        "spread_cost_mode": "one_way",  # 'one_way', 'round_trip'
        "slippage_unit": "percentage",  # 'price', 'pips', 'percentage'
        "slippage_cost_mode": "one_way",  # 'one_way', 'round_trip'
    }


def default_rounding_rules() -> Dict[str, Any]:
    return {
        "equity": "floor_int",
        "forex": "round_2dp",
        "default": "round_2dp",
    }


@dataclass
class CapitalManagementConfig:
    """
    Central configuration object for Capital Management Engine parameters and module toggles.
    """
    base_risk_pct: float = 0.005
    max_trade_risk_pct: float = 0.0075
    max_portfolio_heat_pct: float = 0.05
    max_correlation_adjusted_risk_pct: float = 0.04
    default_stop_method: str = "atr"  # 'atr', 'none'
    default_stop_atr_multiplier: float = 1.5

    heat_policy: str = "reduce"  # 'reduce' or 'reject'
    correlation_fallback_policy: str = "reject"  # 'reject', 'repair', 'assume_zero'
    missing_correlation_policy: str = "reject"  # 'reject', 'repair', 'assume_zero'
    invalid_correlation_policy: str = "reject"  # 'reject', 'repair'
    missing_volatility_policy: str = "conservative"  # 'reject', 'neutral', 'conservative'
    factor_fallback_policy: str = "reject"  # 'reject', 'reduce', 'ignore_module'
    stress_policy: str = "reject"  # 'reject', 'reduce'
    slippage_unit: str = "percentage"  # 'price', 'pips', 'percentage'
    require_verified_instrument_metadata: str = "allow_legacy"  # 'reject' or 'allow_legacy'
    transaction_costs_verified: str = "allowed"  # 'required' or 'allowed'

    drawdown_rules: List[DrawdownRule] = field(default_factory=default_drawdown_rules)
    volatility_rules: List[VolatilityRule] = field(default_factory=default_volatility_rules)
    strategy_allocations: Dict[str, float] = field(default_factory=default_strategy_allocations)
    factor_limits: Dict[str, float] = field(default_factory=default_factor_limits)
    stress_limits: Dict[str, float] = field(default_factory=default_stress_limits)
    transaction_cost_assumptions: Dict[str, Any] = field(default_factory=default_transaction_costs)
    rounding_rules: Dict[str, Any] = field(default_factory=default_rounding_rules)
    modules: Dict[str, bool] = field(default_factory=default_modules_config)
    conviction_risk: ConvictionRiskConfig = field(default_factory=ConvictionRiskConfig)

    def __post_init__(self):
        import math
        if not (0.0 <= self.base_risk_pct <= 1.0):
            raise ValueError(f"base_risk_pct ({self.base_risk_pct}) must be between 0.0 and 1.0")
        if not (0.0 <= self.max_trade_risk_pct <= 1.0):
            raise ValueError(f"max_trade_risk_pct ({self.max_trade_risk_pct}) must be between 0.0 and 1.0")
        if not (0.0 <= self.max_portfolio_heat_pct <= 1.0):
            raise ValueError(f"max_portfolio_heat_pct ({self.max_portfolio_heat_pct}) must be between 0.0 and 1.0")
        if not (0.0 <= self.max_correlation_adjusted_risk_pct <= 1.0):
            raise ValueError(f"max_correlation_adjusted_risk_pct ({self.max_correlation_adjusted_risk_pct}) must be between 0.0 and 1.0")
        if self.slippage_unit.lower() not in ("price", "pips", "percentage"):
            raise ValueError(f"Invalid slippage_unit '{self.slippage_unit}'. Must be 'price', 'pips', or 'percentage'.")
        if self.default_stop_method.lower() not in ("atr", "none"):
            raise ValueError(f"Invalid default_stop_method '{self.default_stop_method}'. Must be 'atr' or 'none'.")
        if not math.isfinite(self.default_stop_atr_multiplier) or self.default_stop_atr_multiplier <= 0:
            raise ValueError(f"default_stop_atr_multiplier ({self.default_stop_atr_multiplier}) must be positive and finite.")

    def is_module_enabled(self, module_name: str) -> bool:
        """
        Checks whether a given risk module is enabled in configuration.
        Supports canonical key aliases ('correlation_risk' / 'correlation_check', 'factor_exposure' / 'factor_check').
        """
        if module_name in ("correlation_risk", "correlation_check"):
            return self.modules.get("correlation_risk", self.modules.get("correlation_check", True))
        if module_name in ("factor_exposure", "factor_check"):
            return self.modules.get("factor_exposure", self.modules.get("factor_check", True))
        return self.modules.get(module_name, True)
