"""
Module 3 — Drawdown Governor.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskTransformer


class DrawdownGovernorModule(RiskTransformer):
    """
    Module 3: Reduces governed risk budget based on portfolio drawdown tiers.

    Formula:
        DD = (Peak Equity - Current Equity) / Peak Equity
        governed_risk_budget = governed_risk_budget * Drawdown Multiplier
    """

    @property
    def name(self) -> str:
        return "drawdown_governor"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        curr = state.account.equity if state.account.equity is not None else state.risk_equity_snapshot
        peak = state.account.peak_equity if (state.account.peak_equity is not None and state.account.peak_equity > 0) else curr
        dd = (peak - curr) / peak if peak is not None and peak > 0 and curr is not None else 0.0
        return {
            "equity": curr,
            "peak_equity": peak,
            "drawdown": dd,
            "prev_governed_budget": state.governed_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "drawdown_multiplier": state.drawdown_multiplier,
            "governed_risk_budget": state.governed_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        curr = state.account.equity if state.account.equity is not None else state.risk_equity_snapshot
        peak = state.account.peak_equity if (state.account.peak_equity is not None and state.account.peak_equity > 0) else curr

        if curr is None or peak is None or peak <= 0 or curr <= 0:
            curr_str = f"${curr:,.2f}" if curr is not None else "None"
            peak_str = f"${peak:,.2f}" if peak is not None else "None"
            state.add_rejection(f"Invalid equity state for drawdown calculation: current={curr_str}, peak={peak_str}")
            state.drawdown_multiplier = 0.0
            state.governed_risk_budget = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason=f"Invalid non-positive equity state (curr={curr_str}, peak={peak_str})",
            )
            return state

        dd = max(0.0, (peak - curr) / peak)

        multiplier = 1.00
        for rule in state.config.drawdown_rules:
            if rule.min_dd <= dd < rule.max_dd:
                multiplier = rule.multiplier
                break

        prev_budget = state.governed_risk_budget
        r1 = prev_budget * multiplier

        state.drawdown_multiplier = multiplier
        state.governed_risk_budget = r1

        msg = f"Drawdown = {dd:.2%}, Multiplier = {multiplier:.2f}, Governed Budget: ${prev_budget:,.2f} -> ${r1:,.2f}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Applied drawdown multiplier {multiplier:.2f} (DD={dd:.2%}), governed budget = ${r1:,.2f}",
        )
        return state
