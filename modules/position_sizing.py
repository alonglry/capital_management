"""
Module 11 — Position Sizing.
"""

import math
from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.transaction_cost import calculate_transaction_cost


class PositionSizingModule(BaseRiskModule):
    """
    Module 11: Converts permitted_risk_budget into theoretical raw_position_size and floor-rounded executable_position_size
    using an integer-step quantity solver.

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
            "max_quantity_binding": getattr(state, "max_quantity_binding", False),
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
        max_qty = inst.max_quantity

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

        # Cap raw size at max_quantity
        max_quantity_binding = raw_size > max_qty + 1e-6
        state.max_quantity_binding = max_quantity_binding

        # 2. Integer-step index solver
        N_raw = math.floor(raw_size / qty_inc)
        N_max = math.floor(max_qty / qty_inc)
        N_min = math.ceil(min_qty / qty_inc)
        N_start = min(N_raw, N_max)

        state.rounded_position_size = float(N_start * qty_inc)

        found_step = None
        for N in range(N_start, N_min - 1, -1):
            q_candidate = float(N * qty_inc)
            stop_risk = inst.calculate_loss_for_price_move(
                state.stop_distance, q_candidate, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
            ) if state.stop_distance > 0 else 0.0
            _, _, _, tx_cost = calculate_transaction_cost(state, q_candidate)
            total_risk = stop_risk + tx_cost

            if total_risk <= budget + 1e-6:
                found_step = q_candidate
                break

        if found_step is None:
            # Check if minimum quantity is complying or rejecting
            q_min = float(N_min * qty_inc)
            stop_risk_min = inst.calculate_loss_for_price_move(
                state.stop_distance, q_min, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
            ) if state.stop_distance > 0 else 0.0
            _, _, _, tx_cost_min = calculate_transaction_cost(state, q_min)
            total_risk_min = stop_risk_min + tx_cost_min

            if total_risk_min > budget + 1e-6:
                status = "REJECT"
                reason = (
                    f"Total risk at minimum broker quantity ({q_min}) (${total_risk_min:,.2f}) "
                    f"exceeds permitted risk budget (${budget:,.2f})"
                )
                state.add_rejection(reason)
                state.executable_position_size = 0.0
                state.final_position_size = 0.0
                state.cost_adjusted_position_size = 0.0
            else:
                executable_size = q_min
                state.executable_position_size = executable_size
                state.final_position_size = executable_size
                state.cost_adjusted_position_size = executable_size
                status = "PASS"
                reason = f"Position size set to minimum broker quantity ({q_min})"
        else:
            executable_size = found_step
            state.executable_position_size = executable_size
            state.final_position_size = executable_size
            state.cost_adjusted_position_size = executable_size
            status = "PASS"
            reason = f"Raw size = {raw_size:,.4f}, Final integer-step executable size = {executable_size:,.4f} (increment={qty_inc})"
            if max_quantity_binding:
                reason += f" [Capped by max_quantity={max_qty}]"

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
