"""
Module 4 — Strategy Allocation.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class StrategyAllocationModule(BaseRiskModule):
    """
    Module 4: Limits risk budget per strategy based on strategy configuration allocations.

    Formula:
        R3 = R_prev * Strategy Multiplier
    """

    @property
    def name(self) -> str:
        return "strategy_allocation"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        strat_id = state.trade.strategy_id
        allocations = state.config.strategy_allocations
        mult = allocations.get(strat_id, allocations.get("default", 1.00))
        return {
            "strategy_id": strat_id,
            "strategy_multiplier": mult,
            "prev_budget": state.adjusted_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "strategy_multiplier": state.strategy_multiplier,
            "adjusted_risk_budget": state.adjusted_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        strat_id = state.trade.strategy_id
        allocations = state.config.strategy_allocations
        multiplier = allocations.get(strat_id, allocations.get("default", 1.00))

        prev_budget = state.adjusted_risk_budget
        r3 = prev_budget * multiplier

        state.strategy_multiplier = multiplier
        state.adjusted_risk_budget = r3

        msg = f"Strategy = '{strat_id}', Multiplier = {multiplier:.2f}, Budget: ${prev_budget:,.2f} -> ${r3:,.2f}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Applied strategy multiplier {multiplier:.2f} for '{strat_id}', adjusted budget = ${r3:,.2f}",
        )
        return state
