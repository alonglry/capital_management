"""
Module 10 — Position Sizing.
"""

import math
from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class PositionSizingModule(BaseRiskModule):
    """
    Module 10: Converts permitted_risk_budget into theoretical raw_position_size and floor-rounded executable_position_size.

    Critical Invariant:
        Never round upward if rounding upward can increase risk.
        executable_position_size = floor(raw_position_size / quantity_increment) * quantity_increment
    """

    @property
    def name(self) -> str:
        return "position_sizing"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "symbol": state.trade.symbol,
            "asset_class": state.trade.asset_class,
            "permitted_risk_budget": state.permitted_risk_budget,
            "stop_distance": state.stop_distance,
            "monetary_risk_per_unit": state.monetary_risk_per_unit,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "raw_position_size": state.raw_position_size,
            "rounded_position_size": state.rounded_position_size,
            "executable_position_size": state.executable_position_size,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        budget = state.permitted_risk_budget
        risk_per_unit = state.monetary_risk_per_unit

        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)

        inst = state.instrument
        qty_inc = inst.quantity_increment
        min_qty = inst.min_quantity

        if budget <= 0 or risk_per_unit <= 0:
            state.raw_position_size = 0.0
            state.rounded_position_size = 0.0
            state.executable_position_size = 0.0
            state.final_position_size = 0.0
            status = "REJECT"
            reason = f"Cannot calculate position size with permitted_risk_budget=${budget:,.2f} or risk_per_unit=${risk_per_unit:,.4f}"
            state.add_rejection(reason)
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status=status,
                reason=reason,
            )
            return state

        # 1. Theoretical raw position size
        raw_size = budget / risk_per_unit

        # 2. Strict Floor Rounding DOWN to quantity_increment
        executable_size = math.floor(raw_size / qty_inc) * qty_inc
        # Clean precision floating point artifacts
        if qty_inc >= 1.0:
            executable_size = float(int(executable_size))
        else:
            decimals = max(0, -int(math.floor(math.log10(qty_inc))))
            executable_size = round(executable_size, decimals)

        state.raw_position_size = raw_size
        state.rounded_position_size = executable_size
        state.executable_position_size = executable_size
        state.cost_adjusted_position_size = executable_size
        state.final_position_size = executable_size

        # 3. Check Minimum Quantity Constraint
        if executable_size < min_qty:
            risk_at_min = min_qty * risk_per_unit
            if risk_at_min > budget:
                status = "REJECT"
                reason = f"Calculated size ({raw_size:.4f}) is below minimum broker quantity ({min_qty}). Risk at minimum quantity (${risk_at_min:,.2f}) exceeds permitted budget (${budget:,.2f})"
                state.add_rejection(reason)
                state.executable_position_size = 0.0
                state.final_position_size = 0.0
            else:
                executable_size = min_qty
                state.executable_position_size = executable_size
                state.final_position_size = executable_size
                status = "PASS"
                reason = f"Floor rounded size set to minimum quantity ({min_qty})"
        else:
            status = "PASS"
            reason = f"Raw size = {raw_size:,.4f}, Floor-rounded size = {executable_size:,.4f} (increment={qty_inc})"

        msg = f"Budget = ${budget:,.2f}, Risk/Unit = ${risk_per_unit:,.4f} -> Raw = {raw_size:,.4f}, Executable = {state.executable_position_size:,.4f}"
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
