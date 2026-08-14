"""
Module 10 — Position Sizing.
"""

import math
from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.transaction_cost import calculate_transaction_cost


class PositionSizingModule(BaseRiskModule):
    """
    Module 10: Converts permitted_risk_budget into theoretical raw_position_size and floor-rounded executable_position_size.

    Enforces sizing + transaction cost iteration loop ensuring:
        stop_loss_risk(quantity) + transaction_cost(quantity) <= permitted_risk_budget
    """

    @property
    def name(self) -> str:
        return "position_sizing"

    @property
    def module_type(self) -> str:
        return "sizing"

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

        # Validate broker rules explicitly
        is_valid_broker, msg_broker = inst.validate_broker_rules()
        if not is_valid_broker:
            state.raw_position_size = 0.0
            state.rounded_position_size = 0.0
            state.executable_position_size = 0.0
            state.final_position_size = 0.0
            status = "REJECT"
            reason = f"Broker rule validation failed: {msg_broker}"
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

        # 1. Theoretical raw position size based on stop loss risk alone
        raw_size = budget / risk_per_unit
        state.raw_position_size = raw_size

        # 2. Strict Floor Rounding DOWN to quantity_increment
        executable_size = math.floor(raw_size / qty_inc) * qty_inc
        if qty_inc >= 1.0:
            executable_size = float(int(executable_size))
        else:
            decimals = max(0, -int(math.floor(math.log10(qty_inc))))
            executable_size = round(executable_size, decimals)

        state.rounded_position_size = executable_size

        # 3. Check Minimum Quantity & Cost Iteration Loop
        if executable_size < min_qty:
            test_size = min_qty
            stop_risk_min = test_size * risk_per_unit
            _, _, _, tx_cost_min = calculate_transaction_cost(state, test_size)
            total_risk_min = stop_risk_min + tx_cost_min

            if total_risk_min > budget + 1e-6:
                status = "REJECT"
                reason = (
                    f"Calculated raw size ({raw_size:.4f}) is below minimum broker quantity ({min_qty}). "
                    f"Total risk at minimum quantity (${total_risk_min:,.2f} = stop ${stop_risk_min:,.2f} + cost ${tx_cost_min:,.2f}) "
                    f"exceeds permitted risk budget (${budget:,.2f})"
                )
                state.add_rejection(reason)
                state.executable_position_size = 0.0
                state.final_position_size = 0.0
                state.cost_adjusted_position_size = 0.0
            else:
                executable_size = min_qty
                state.executable_position_size = executable_size
                state.final_position_size = executable_size
                state.cost_adjusted_position_size = executable_size
                status = "PASS"
                reason = f"Position size set to minimum broker quantity ({min_qty}) with total risk (${total_risk_min:,.2f}) <= budget (${budget:,.2f})"
        else:
            # Iterative step-down loop including transaction costs
            curr_size = executable_size
            while curr_size >= min_qty:
                stop_risk = curr_size * risk_per_unit
                _, _, _, tx_cost = calculate_transaction_cost(state, curr_size)
                total_risk = stop_risk + tx_cost

                if total_risk <= budget + 1e-6:
                    break

                # Step down by quantity increment
                next_size = curr_size - qty_inc
                if qty_inc >= 1.0:
                    curr_size = float(int(round(next_size)))
                else:
                    decimals = max(0, -int(math.floor(math.log10(qty_inc))))
                    curr_size = round(next_size, decimals)

            if curr_size < min_qty:
                status = "REJECT"
                reason = f"Total risk including transaction costs exceeded permitted budget (${budget:,.2f}) and could not be stepped down above min_quantity ({min_qty})"
                state.add_rejection(reason)
                state.executable_position_size = 0.0
                state.final_position_size = 0.0
                state.cost_adjusted_position_size = 0.0
            else:
                executable_size = curr_size
                state.executable_position_size = executable_size
                state.final_position_size = executable_size
                state.cost_adjusted_position_size = executable_size
                status = "PASS"
                reason = f"Raw size = {raw_size:,.4f}, Final cost-adjusted executable size = {executable_size:,.4f} (increment={qty_inc})"

        msg = f"Budget = ${budget:,.2f}, Risk/Unit = ${risk_per_unit:,.4f} -> Raw = {raw_size:,.4f}, Executable = {state.executable_position_size:,.4f}, Status = {status}"
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
