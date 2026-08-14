"""
Formal Structured Ledgers for Risk Accounting and Capacities.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RiskLedger:
    """
    Canonical risk ledger tracking all components of normal and stress risk.
    """
    stop_loss_risk: float = 0.0
    transaction_cost: float = 0.0
    financing_cost: float = 0.0
    short_borrow_cost: float = 0.0
    normal_total_risk: float = 0.0
    incremental_gap_loss: float = 0.0
    incremental_stress_slippage_loss: float = 0.0
    stress_total_risk: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "stop_loss_risk": self.stop_loss_risk,
            "transaction_cost": self.transaction_cost,
            "financing_cost": self.financing_cost,
            "short_borrow_cost": self.short_borrow_cost,
            "normal_total_risk": self.normal_total_risk,
            "incremental_gap_loss": self.incremental_gap_loss,
            "incremental_stress_slippage_loss": self.incremental_stress_slippage_loss,
            "stress_total_risk": self.stress_total_risk,
        }


@dataclass
class RiskCapacityLedger:
    """
    Canonical risk capacity ledger tracking pre-sizing and final constraint capacities.
    """
    trade_capacity: float = float("inf")
    portfolio_heat_capacity: float = float("inf")
    correlation_capacity: float = float("inf")
    factor_capacity: float = float("inf")
    stress_capacity: float = float("inf")
    permitted_capacity: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "trade_capacity": self.trade_capacity,
            "portfolio_heat_capacity": self.portfolio_heat_capacity,
            "correlation_capacity": self.correlation_capacity,
            "factor_capacity": self.factor_capacity,
            "stress_capacity": self.stress_capacity,
            "permitted_capacity": self.permitted_capacity,
        }
