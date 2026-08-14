"""
Shared pipeline state and module result data models.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.trade_candidate import TradeCandidate


@dataclass
class ModuleResult:
    """
    Structured outcome produced by each executed module in the pipeline.

    Args:
        module_name (str): Identifier of the module.
        enabled (bool): Whether the module was enabled during execution.
        input_summary (Dict[str, Any]): Summary snapshot of inputs consumed.
        output_summary (Dict[str, Any]): Summary snapshot of metrics updated.
        status (str): Outcome status ('PASS', 'FAIL', 'REJECT', 'SKIPPED', 'WARNING').
        reason (str): Human-readable explanation of module result.
    """
    module_name: str
    enabled: bool
    input_summary: Dict[str, Any]
    output_summary: Dict[str, Any]
    status: str
    reason: str


@dataclass
class CapitalManagementState:
    """
    Mutable state object passed along the capital management pipeline.
    Preserves all inputs, intermediate calculations, step metrics, capacities, and logs.
    """
    # Inputs
    account: AccountState
    portfolio: List[Position]
    trade: TradeCandidate
    market_data: MarketData
    config: CapitalManagementConfig
    instrument: Optional[InstrumentSpec] = None

    # Explicit Risk Budget Stages
    base_risk_budget: float = 0.0
    requested_risk_budget: float = 0.0
    requested_risk_pct: float = 0.0
    governed_risk_budget: float = 0.0

    # Constraint Risk Capacities
    trade_risk_capacity: float = float("inf")
    portfolio_heat_capacity: float = float("inf")
    correlation_risk_capacity: float = float("inf")
    factor_risk_capacity: float = float("inf")
    stress_risk_capacity: float = float("inf")

    # Final Permitted Risk Budget
    permitted_risk_budget: float = 0.0

    # Conviction Metrics
    long_conviction: Any = 0.0
    short_conviction: Any = 0.0
    net_conviction: Any = 0.0
    directional_strength: Any = 0.0
    signal_conflict: Any = 0.0
    conviction_multiplier: Any = 1.0
    conflict_multiplier: Any = 1.0

    # Governor Multipliers
    drawdown_multiplier: float = 1.0
    volatility_multiplier: float = 1.0
    strategy_multiplier: float = 1.0

    # Portfolio Heat Metrics
    current_portfolio_heat: float = 0.0
    projected_portfolio_heat: float = 0.0
    remaining_portfolio_risk_capacity: float = 0.0

    # Correlation Metrics
    correlation_adjusted_risk: float = 0.0
    projected_correlation_adjusted_risk: float = 0.0

    # Factor Exposure Metrics
    factor_exposure: Dict[str, float] = field(default_factory=dict)
    current_factor_exposure: Dict[str, float] = field(default_factory=dict)
    projected_factor_exposure: Dict[str, float] = field(default_factory=dict)
    factor_limit_utilization: Dict[str, float] = field(default_factory=dict)
    factor_constraint_status: str = "PASS"

    # Stop Loss Metrics
    stop_distance: float = 0.0
    stop_distance_pct: float = 0.0
    stop_method: str = "price"
    monetary_risk_per_unit: float = 0.0

    # Sizing & Execution Metrics
    raw_position_size: float = 0.0
    rounded_position_size: float = 0.0
    executable_position_size: float = 0.0

    # Cost Metrics
    estimated_spread_cost: float = 0.0
    estimated_commission: float = 0.0
    estimated_slippage: float = 0.0
    total_transaction_cost: float = 0.0
    cost_adjusted_position_size: float = 0.0

    # Stress Metrics
    normal_loss: float = 0.0
    stress_loss: float = 0.0
    stress_loss_pct: float = 0.0

    # Actual Reconciled Risk Outputs
    actual_stop_loss_risk: float = 0.0
    actual_transaction_cost: float = 0.0
    actual_total_risk: float = 0.0

    # Final Gate Output Metrics
    final_position_size: float = 0.0
    final_risk: float = 0.0
    final_risk_pct: float = 0.0
    approved: bool = False

    # Pipeline Trace & Auditing
    module_results: Dict[str, ModuleResult] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    trace_logs: List[str] = field(default_factory=list)

    @property
    def adjusted_risk_budget(self) -> float:
        """
        Backward-compatibility alias returning governed_risk_budget or permitted_risk_budget.
        """
        return self.governed_risk_budget

    @adjusted_risk_budget.setter
    def adjusted_risk_budget(self, val: float) -> None:
        """
        Backward-compatibility setter updating governed_risk_budget and permitted_risk_budget.
        """
        self.governed_risk_budget = val
        self.permitted_risk_budget = val

    def add_trace(self, tag: str, message: str) -> None:
        """
        Appends a formatted trace line to trace_logs.
        """
        line = f"[{tag}] {message}"
        self.trace_logs.append(line)

    def add_warning(self, message: str) -> None:
        """
        Appends a warning message.
        """
        if message not in self.warnings:
            self.warnings.append(message)

    def add_rejection(self, reason: str) -> None:
        """
        Appends a rejection reason.
        """
        if reason not in self.rejection_reasons:
            self.rejection_reasons.append(reason)
