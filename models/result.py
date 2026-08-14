"""
Final Capital Management Result data model.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from capital_management.models.state import ModuleResult


@dataclass
class CapitalManagementResult:
    """
    Structured outcome returned by the Capital Management Engine.
    Contains explicit risk accounting stages, capacities, position sizes, actual risks,
    rejection reasons, warnings, binding constraints, ledgers, per-module outcome records, and complete calculation trace.
    """
    approved: bool
    symbol: str
    side: str
    asset_class: str

    base_risk_budget: float
    requested_risk_budget: float
    requested_risk_pct: float
    governed_risk_budget: float

    trade_risk_capacity: float
    portfolio_heat_capacity: float
    correlation_risk_capacity: float
    factor_risk_capacity: float
    stress_risk_capacity: float
    permitted_risk_budget: float

    raw_position_size: float
    executable_position_size: float
    attempted_position_size: float
    final_position_size: float

    entry_price: float
    stop_price: float
    stop_distance: float

    actual_stop_loss_risk: float
    actual_transaction_cost: float
    actual_total_risk: float
    final_risk_budget: float
    final_risk_pct: float

    current_portfolio_heat: float
    projected_portfolio_heat: float

    correlation_adjusted_risk: float
    factor_exposure: Dict[str, float]

    transaction_cost: float
    stress_loss: float

    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    module_results: Dict[str, ModuleResult] = field(default_factory=dict)
    calculation_trace: List[str] = field(default_factory=list)
    binding_constraints: List[str] = field(default_factory=list)

    risk_ledger: Dict[str, float] = field(default_factory=dict)
    risk_capacity_ledger: Dict[str, float] = field(default_factory=dict)
    attempted_risk_ledger: Dict[str, float] = field(default_factory=dict)

    engine_version: str = "2.1.0"
    risk_equity_snapshot: float = 0.0
    calculation_input_hash: str = ""
    as_of_timestamp: Optional[str] = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def correlation_adjusted_stop_risk_pct(self) -> float:
        return self.correlation_adjusted_risk

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts result object to a clean dictionary representation.
        """
        return {
            "approved": self.approved,
            "symbol": self.symbol,
            "side": self.side,
            "asset_class": self.asset_class,
            "base_risk_budget": self.base_risk_budget,
            "requested_risk_budget": self.requested_risk_budget,
            "requested_risk_pct": self.requested_risk_pct,
            "governed_risk_budget": self.governed_risk_budget,
            "trade_risk_capacity": self.trade_risk_capacity,
            "portfolio_heat_capacity": self.portfolio_heat_capacity,
            "correlation_risk_capacity": self.correlation_risk_capacity,
            "factor_risk_capacity": self.factor_risk_capacity,
            "stress_risk_capacity": self.stress_risk_capacity,
            "permitted_risk_budget": self.permitted_risk_budget,
            "raw_position_size": self.raw_position_size,
            "executable_position_size": self.executable_position_size,
            "attempted_position_size": self.attempted_position_size,
            "final_position_size": self.final_position_size,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "stop_distance": self.stop_distance,
            "actual_stop_loss_risk": self.actual_stop_loss_risk,
            "actual_transaction_cost": self.actual_transaction_cost,
            "actual_total_risk": self.actual_total_risk,
            "final_risk_budget": self.final_risk_budget,
            "final_risk_pct": self.final_risk_pct,
            "current_portfolio_heat": self.current_portfolio_heat,
            "projected_portfolio_heat": self.projected_portfolio_heat,
            "correlation_adjusted_risk": self.correlation_adjusted_risk,
            "correlation_adjusted_stop_risk_pct": self.correlation_adjusted_stop_risk_pct,
            "factor_exposure": self.factor_exposure,
            "transaction_cost": self.transaction_cost,
            "stress_loss": self.stress_loss,
            "rejection_reasons": self.rejection_reasons,
            "warnings": self.warnings,
            "binding_constraints": self.binding_constraints,
            "risk_ledger": self.risk_ledger,
            "risk_capacity_ledger": self.risk_capacity_ledger,
            "attempted_risk_ledger": self.attempted_risk_ledger,
            "engine_version": self.engine_version,
            "risk_equity_snapshot": self.risk_equity_snapshot,
            "calculation_input_hash": self.calculation_input_hash,
            "as_of_timestamp": self.as_of_timestamp,
            "module_results": {
                name: {
                    "module_name": res.module_name,
                    "enabled": res.enabled,
                    "input_summary": res.input_summary,
                    "output_summary": res.output_summary,
                    "status": res.status,
                    "reason": res.reason,
                }
                for name, res in self.module_results.items()
            },
            "calculation_trace": self.calculation_trace,
        }
