"""
Final Capital Management Result data model.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from capital_management.models.state import ModuleResult


@dataclass
class CapitalManagementResult:
    """
    Structured outcome returned by the Capital Management Engine.
    Contains decision result, sizing numbers, risk allocations, warnings, rejection reasons,
    per-module outcome records, and complete calculation trace.
    """
    approved: bool
    symbol: str
    side: str
    asset_class: str

    raw_position_size: float
    final_position_size: float

    entry_price: float
    stop_price: float
    stop_distance: float

    base_risk_budget: float
    requested_risk_budget: float
    requested_risk_pct: float
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

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts result object to a clean dictionary representation.
        """
        return {
            "approved": self.approved,
            "symbol": self.symbol,
            "side": self.side,
            "asset_class": self.asset_class,
            "raw_position_size": self.raw_position_size,
            "final_position_size": self.final_position_size,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "stop_distance": self.stop_distance,
            "base_risk_budget": self.base_risk_budget,
            "requested_risk_budget": self.requested_risk_budget,
            "requested_risk_pct": self.requested_risk_pct,
            "final_risk_budget": self.final_risk_budget,
            "final_risk_pct": self.final_risk_pct,
            "current_portfolio_heat": self.current_portfolio_heat,
            "projected_portfolio_heat": self.projected_portfolio_heat,
            "correlation_adjusted_risk": self.correlation_adjusted_risk,
            "factor_exposure": self.factor_exposure,
            "transaction_cost": self.transaction_cost,
            "stress_loss": self.stress_loss,
            "rejection_reasons": self.rejection_reasons,
            "warnings": self.warnings,
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
