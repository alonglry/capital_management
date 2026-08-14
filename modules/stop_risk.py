"""
Module 8 — Stop-Loss Risk Calculation.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class StopRiskModule(BaseRiskModule):
    """
    Module 8: Calculates absolute stop distance and percentage stop risk from trade parameters.

    Formula:
        stop_distance = abs(entry_price - proposed_stop_price)
        stop_distance_pct = stop_distance / entry_price
    """

    @property
    def name(self) -> str:
        return "stop_risk"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "entry_price": state.trade.entry_price,
            "proposed_stop_price": state.trade.proposed_stop_price,
            "side": state.trade.side,
            "asset_class": state.trade.asset_class,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "stop_distance": state.stop_distance,
            "stop_distance_pct": state.stop_distance_pct,
            "stop_method": state.stop_method,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        entry = state.trade.entry_price
        stop = state.trade.proposed_stop_price

        if entry <= 0:
            state.add_rejection("Trade candidate entry_price must be > 0.")
            status = "REJECT"
            reason = "Invalid entry_price <= 0"
        else:
            dist = abs(entry - stop)
            dist_pct = dist / entry

            state.stop_distance = dist
            state.stop_distance_pct = dist_pct
            state.stop_method = "price"

            if dist == 0:
                status = "REJECT"
                reason = "Proposed stop price equals entry price (stop_distance = 0)"
                state.add_rejection(reason)
            else:
                status = "PASS"
                reason = f"Calculated stop distance = {dist:,.5f} ({dist_pct:.2%})"

        msg = f"Entry = {entry}, Stop = {stop}, Stop Distance = {state.stop_distance:,.5f} ({state.stop_distance_pct:.2%}), Status = {status}"
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
