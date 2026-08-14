"""
Module 1 — Base Risk Budget.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskTransformer


class BaseRiskBudgetModule(RiskTransformer):
    """
    Module 1: Calculates initial monetary risk budget.

    Formula:
        base_risk_budget = Equity * Base Risk %
    """

    @property
    def name(self) -> str:
        return "base_risk"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "equity": state.account.equity,
            "base_risk_pct": state.config.base_risk_pct,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "base_risk_budget": state.base_risk_budget,
            "governed_risk_budget": state.governed_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        base_risk_pct = state.config.base_risk_pct

        if equity <= 0:
            state.add_rejection(f"Account equity is non-positive ({equity:,.2f})")
            state.base_risk_budget = 0.0
            state.requested_risk_budget = 0.0
            state.governed_risk_budget = 0.0
            state.permitted_risk_budget = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason=f"Account equity is non-positive ({equity:,.2f})",
            )
            return state

        r0 = equity * base_risk_pct
        state.base_risk_budget = r0
        state.requested_risk_budget = r0
        state.governed_risk_budget = r0
        state.permitted_risk_budget = r0

        msg = f"Equity = ${equity:,.2f}, Base Risk % = {base_risk_pct:.4f} -> Base Risk Budget R0 = ${r0:,.2f}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Calculated base risk budget R0 = ${r0:,.2f}",
        )
        return state


# Backward-compatibility alias
BaseRiskModule = BaseRiskBudgetModule
