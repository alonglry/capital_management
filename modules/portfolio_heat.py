"""
Module 5 — Portfolio Heat.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class PortfolioHeatModule(BaseRiskModule):
    """
    Module 5: Evaluates current and projected total portfolio heat (risk / equity).

    Formula:
        Current Heat = sum(position_monetary_risk_i) / Equity
        Projected Heat = (sum(position_monetary_risk_i) + candidate_risk_budget) / Equity
    """

    @property
    def name(self) -> str:
        return "portfolio_heat"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        equity = state.account.equity
        curr_heat_monetary = sum(p.monetary_risk_at_stop for p in state.portfolio)
        curr_heat_pct = curr_heat_monetary / equity if equity > 0 else 0.0
        return {
            "equity": equity,
            "current_portfolio_heat_pct": curr_heat_pct,
            "max_portfolio_heat_pct": state.config.max_portfolio_heat_pct,
            "candidate_risk_budget": state.adjusted_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "current_portfolio_heat": state.current_portfolio_heat,
            "projected_portfolio_heat": state.projected_portfolio_heat,
            "remaining_portfolio_risk_capacity": state.remaining_portfolio_risk_capacity,
            "adjusted_risk_budget": state.adjusted_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        if equity <= 0:
            state.add_rejection("Account equity is zero or negative.")
            return state

        max_heat_pct = state.config.max_portfolio_heat_pct
        max_heat_monetary = equity * max_heat_pct

        curr_heat_monetary = sum(p.monetary_risk_at_stop for p in state.portfolio)
        curr_heat_pct = curr_heat_monetary / equity

        remaining_monetary_capacity = max(0.0, max_heat_monetary - curr_heat_monetary)
        remaining_pct_capacity = remaining_monetary_capacity / equity

        proposed_budget = state.adjusted_risk_budget
        projected_heat_monetary = curr_heat_monetary + proposed_budget
        projected_heat_pct = projected_heat_monetary / equity

        state.current_portfolio_heat = curr_heat_pct
        state.remaining_portfolio_risk_capacity = remaining_monetary_capacity

        status = "PASS"
        reason = f"Projected portfolio heat {projected_heat_pct:.2%} is within maximum limit {max_heat_pct:.2%}"

        if projected_heat_pct > max_heat_pct:
            if state.config.heat_policy == "reject":
                status = "REJECT"
                reason = f"Projected portfolio heat = {projected_heat_pct:.2%}, limit = {max_heat_pct:.2%}"
                state.add_rejection(reason)
            else:  # 'reduce' policy
                if remaining_monetary_capacity <= 0:
                    status = "REJECT"
                    reason = f"Current portfolio heat {curr_heat_pct:.2%} meets or exceeds maximum limit {max_heat_pct:.2%}"
                    state.add_rejection(reason)
                else:
                    new_budget = remaining_monetary_capacity
                    state.add_warning(
                        f"Reduced risk budget from ${proposed_budget:,.2f} to ${new_budget:,.2f} due to portfolio heat cap ({max_heat_pct:.2%})"
                    )
                    state.adjusted_risk_budget = new_budget
                    projected_heat_pct = (curr_heat_monetary + new_budget) / equity
                    status = "PASS"
                    reason = f"Cap applied: risk budget reduced to ${new_budget:,.2f} to keep heat at {projected_heat_pct:.2%}"

        state.projected_portfolio_heat = projected_heat_pct

        msg = f"Current Heat = {curr_heat_pct:.2%}, Projected Heat = {projected_heat_pct:.2%}, Limit = {max_heat_pct:.2%}, Status = {status}"
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
