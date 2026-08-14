"""
Module 11 — Position Sizing.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.quantity_solver import solve_max_executable_quantity
from capital_management.modules.transaction_cost import calculate_transaction_cost


class PositionSizingModule(BaseRiskModule):
    """
    Module 11: Converts permitted_risk_budget into theoretical raw_position_size and executable_position_size
    using the canonical solve_max_executable_quantity solver.
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

        inst = state.instrument
        if inst is None:
            state.add_rejection("Missing required explicit InstrumentSpec metadata.")
            state.executable_position_size = 0.0
            state.final_position_size = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Missing required explicit InstrumentSpec metadata.",
            )
            return state

        # Unconditionally validate InstrumentSpec metadata for capital management
        is_valid_spec, msg_spec = inst.validate_for_capital_management(state.account.currency, state.trade)
        if not is_valid_spec:
            state.raw_position_size = 0.0
            state.rounded_position_size = 0.0
            state.executable_position_size = 0.0
            state.final_position_size = 0.0
            status = "REJECT"
            reason = f"Instrument validation failed: {msg_spec}"
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

        if qty_inc is None or min_qty is None or max_qty is None:
            state.add_rejection("InstrumentSpec quantity rules (quantity_increment, min_quantity, max_quantity) must not be None.")
            state.executable_position_size = 0.0
            state.final_position_size = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Missing InstrumentSpec quantity rules.",
            )
            return state

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
        state.max_quantity_binding = raw_size > max_qty + 1e-6

        # 2. Risk evaluation function combining stop loss risk and canonical transaction costs
        def total_risk_fn(q: float) -> float:
            stop_r = inst.calculate_loss_for_price_move(
                state.stop_distance, q, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
            ) if state.stop_distance > 0 else 0.0
            _, _, _, tx_c = calculate_transaction_cost(state, q)
            return stop_r + tx_c

        # 3. Call single canonical solver
        executable_size, is_satisfied = solve_max_executable_quantity(
            total_risk_fn, budget, min_qty, max_qty, qty_inc
        )

        if not is_satisfied or executable_size < min_qty:
            status = "REJECT"
            reason = f"Total risk at minimum broker quantity ({min_qty}) exceeds permitted risk budget (${budget:,.2f})"
            state.add_rejection(reason)
            state.executable_position_size = 0.0
            state.attempted_position_size = 0.0
            state.final_position_size = 0.0
            state.cost_adjusted_position_size = 0.0
        else:
            state.executable_position_size = executable_size
            state.attempted_position_size = executable_size
            state.final_position_size = executable_size
            state.cost_adjusted_position_size = executable_size
            state.rounded_position_size = executable_size
            status = "PASS"
            reason = f"Raw size = {raw_size:,.4f}, Final canonical executable size = {executable_size:,.4f} (increment={qty_inc})"

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
