"""
Shared pipeline state and module result data models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.ledger import RiskCapacityLedger, RiskLedger
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.trade_candidate import TradeCandidate


@dataclass
class ModuleResult:
    """
    Structured outcome produced by each executed module in the pipeline.
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
    """
    # Inputs
    account: AccountState
    portfolio: List[Position]
    trade: TradeCandidate
    market_data: MarketData
    config: CapitalManagementConfig
    instrument: Optional[InstrumentSpec] = None

    # Immutable Snapshots & Timestamps
    risk_equity_snapshot: float = 0.0
    decision_timestamp: Optional[str] = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    calculation_input_hash: str = ""

    # Formal Ledgers
    risk_ledger: RiskLedger = field(default_factory=RiskLedger)
    risk_capacity_ledger: RiskCapacityLedger = field(default_factory=RiskCapacityLedger)
    attempted_risk_ledger: RiskLedger = field(default_factory=RiskLedger)

    # Explicit Risk Budget Stages
    risk_capital_base: float = 0.0
    risk_capital_source: str = "unavailable"
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
    binding_constraints: List[str] = field(default_factory=list)

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
    proposed_stop_price: Optional[float] = None
    effective_stop_price: Optional[float] = None
    stop_price_source: Optional[str] = None
    stop_distance: float = 0.0
    stop_distance_pct: float = 0.0
    stop_method: str = "price"
    monetary_risk_per_unit: float = 0.0

    # Sizing & Execution Metrics
    raw_position_size: float = 0.0
    rounded_position_size: float = 0.0
    executable_position_size: float = 0.0
    attempted_position_size: float = 0.0
    max_quantity_binding: bool = False

    # Cost Metrics
    estimated_spread_cost: float = 0.0
    estimated_commission: float = 0.0
    estimated_slippage: float = 0.0
    total_transaction_cost: float = 0.0
    cost_adjusted_position_size: float = 0.0
    short_borrow_cost: float = 0.0
    financing_cost: float = 0.0

    # Stress Metrics
    normal_stop_loss_risk: float = 0.0
    normal_transaction_cost: float = 0.0
    normal_total_risk: float = 0.0
    normal_loss: float = 0.0
    incremental_gap_loss: float = 0.0
    incremental_stress_slippage_loss: float = 0.0
    stress_total_risk: float = 0.0
    stress_loss: float = 0.0
    stress_loss_pct: float = 0.0
    stress_direction: str = "adverse_down"
    stressed_exit_price: float = 0.0

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

    def __post_init__(self):
        if self.risk_equity_snapshot <= 0 and self.account:
            eq = getattr(self.account, "equity", None)
            if eq is not None and isinstance(eq, (int, float)) and math.isfinite(eq) and eq > 0:
                self.risk_equity_snapshot = float(eq)

    @property
    def correlation_adjusted_stop_risk_pct(self) -> float:
        return self.correlation_adjusted_risk

    @property
    def projected_correlation_adjusted_stop_risk_pct(self) -> float:
        return self.projected_correlation_adjusted_risk

    @property
    def adjusted_risk_budget(self) -> float:
        return self.governed_risk_budget

    @adjusted_risk_budget.setter
    def adjusted_risk_budget(self, val: float) -> None:
        self.governed_risk_budget = val
        self.permitted_risk_budget = val

    def add_trace(self, tag: str, message: str) -> None:
        line = f"[{tag}] {message}"
        self.trace_logs.append(line)

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def add_rejection(self, reason: str) -> None:
        if reason not in self.rejection_reasons:
            self.rejection_reasons.append(reason)
