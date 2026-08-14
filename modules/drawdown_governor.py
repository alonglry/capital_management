"""
Module 2 — Drawdown Governor.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class DrawdownGovernorModule(BaseRiskModule):
    """
    Module 2: Reduces risk budget based on portfolio drawdown tiers.

    Formula:
        DD = (Peak Equity - Current Equity) / Peak Equity
        R1 = R_prev * Drawdown Multiplier
    """

    @property
    def name(self) -> str:
        return "drawdown_governor"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        peak = state.account.get_peak_equity()
        curr = state.account.equity
        dd = (peak - curr) / peak if peak > 0 else 0.0
        return {
            "equity": curr,
            "peak_equity": peak,
            "drawdown": dd,
            "prev_budget": state.adjusted_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "drawdown_multiplier": state.drawdown_multiplier,
            "adjusted_risk_budget": state.adjusted_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        peak = state.account.get_peak_equity()
        curr = state.account.equity
        dd = max(0.0, (peak - curr) / peak) if peak > 0 else 0.0

        multiplier = 1.00
        for rule in state.config.drawdown_rules:
            if rule.min_dd <= dd < rule.max_dd:
                multiplier = rule.multiplier
                break

        prev_budget = state.adjusted_risk_budget
        r1 = prev_budget * multiplier

        state.drawdown_multiplier = multiplier
        state.adjusted_risk_budget = r1

        msg = f"Drawdown = {dd:.2%}, Multiplier = {multiplier:.2f}, Budget: ${prev_budget:,.2f} -> ${r1:,.2f}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Applied drawdown multiplier {multiplier:.2f} (DD={dd:.2%}), adjusted budget = ${r1:,.2f}",
        )
        return state
