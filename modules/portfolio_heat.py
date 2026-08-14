"""
Module 6 — Portfolio Heat.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskConstraint


class PortfolioHeatModule(RiskConstraint):
    """
    Module 6: Hard risk constraint enforcing stop-loss portfolio heat limits.

    Formula:
        current_heat = sum(existing_position_monetary_risk) / account_equity
        portfolio_heat_capacity = max(0, account_equity * max_portfolio_heat - existing_position_monetary_risk)
        permitted_risk_budget = min(permitted_risk_budget, portfolio_heat_capacity)
    """

    @property
    def name(self) -> str:
        return "portfolio_heat"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        equity = state.risk_equity_snapshot
        curr_risk = sum(p.monetary_risk_at_stop for p in state.portfolio)
        curr_heat_pct = curr_risk / equity if equity > 0 else 0.0
        return {
            "equity": equity,
            "existing_position_risk": curr_risk,
            "current_stop_loss_heat": curr_heat_pct,
            "max_portfolio_heat_pct": state.config.max_portfolio_heat_pct,
            "permitted_risk_budget_before": state.permitted_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "portfolio_heat_capacity": state.portfolio_heat_capacity,
            "permitted_risk_budget": state.permitted_risk_budget,
            "current_portfolio_heat": state.current_portfolio_heat,
            "projected_portfolio_heat": state.projected_portfolio_heat,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.risk_equity_snapshot
        if equity <= 0:
            state.add_rejection("Account equity is non-positive for portfolio heat calculation.")
            state.portfolio_heat_capacity = 0.0
            state.permitted_risk_budget = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Account equity is non-positive",
            )
            return state

        for p in state.portfolio:
            if p.monetary_risk_at_stop < 0 or not math.isfinite(p.monetary_risk_at_stop):
                state.add_rejection(f"Invalid negative or non-finite monetary risk at stop ({p.monetary_risk_at_stop}) for position {p.symbol}")
                state.portfolio_heat_capacity = 0.0
                state.permitted_risk_budget = 0.0
                state.module_results[self.name] = ModuleResult(
                    module_name=self.name,
                    enabled=True,
                    input_summary=self._get_input_summary(state),
                    output_summary=self._get_output_summary(state),
                    status="REJECT",
                    reason=f"Invalid position monetary risk for {p.symbol}",
                )
                return state

        max_heat_pct = state.config.max_portfolio_heat_pct
        max_monetary_heat = equity * max_heat_pct

        existing_risk = sum(p.monetary_risk_at_stop for p in state.portfolio)
        current_heat_pct = existing_risk / equity

        heat_capacity = max(0.0, max_monetary_heat - existing_risk)
        state.portfolio_heat_capacity = heat_capacity
        state.current_portfolio_heat = current_heat_pct

        prev_permitted = state.permitted_risk_budget
        new_permitted = min(prev_permitted, heat_capacity)
        state.permitted_risk_budget = new_permitted

        projected_heat_pct = (existing_risk + new_permitted) / equity
        state.projected_portfolio_heat = projected_heat_pct

        if heat_capacity <= 0:
            status = "REJECT"
            reason = f"Current portfolio heat ({current_heat_pct:.2%}) meets or exceeds maximum limit ({max_heat_pct:.2%})"
            state.add_rejection(reason)
        elif new_permitted < prev_permitted:
            status = "PASS"
            reason = f"Portfolio heat constraint reduced permitted risk from ${prev_permitted:,.2f} to ${new_permitted:,.2f} (capacity = ${heat_capacity:,.2f})"
            state.add_warning(reason)
        else:
            status = "PASS"
            reason = f"Portfolio heat capacity (${heat_capacity:,.2f}) satisfies requested permitted risk (${new_permitted:,.2f})"

        msg = f"Current Heat = {current_heat_pct:.2%}, Capacity = ${heat_capacity:,.2f}, Permitted Risk: ${prev_permitted:,.2f} -> ${new_permitted:,.2f}, Status = {status}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status=status,
            reason=reason,
        )
        return state
