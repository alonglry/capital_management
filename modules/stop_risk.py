"""
Module 9 — Stop-Loss Risk Calculation.
"""

from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class StopRiskModule(BaseRiskModule):
    """
    Module 9: Calculates stop distance and monetary risk per unit using InstrumentSpec.
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
            "monetary_risk_per_unit": state.monetary_risk_per_unit,
            "stop_method": state.stop_method,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        entry = state.trade.entry_price
        stop = state.trade.proposed_stop_price

        # Resolve or create InstrumentSpec
        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)

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

            if dist <= 0:
                status = "REJECT"
                reason = "Proposed stop price equals or exceeds entry price (stop_distance <= 0)"
                state.add_rejection(reason)
            else:
                pip_val = state.trade.pip_value_per_lot
                monetary_risk_per_unit = state.instrument.calculate_monetary_risk_per_unit(entry, stop, pip_val)
                state.monetary_risk_per_unit = monetary_risk_per_unit
                status = "PASS"
                reason = f"Calculated stop distance = {dist:,.5f} ({dist_pct:.2%}), monetary risk per unit = ${monetary_risk_per_unit:,.4f}"

        msg = f"Entry = {entry}, Stop = {stop}, Stop Distance = {state.stop_distance:,.5f} ({state.stop_distance_pct:.2%}), Risk/Unit = ${state.monetary_risk_per_unit:,.4f}, Status = {status}"
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
