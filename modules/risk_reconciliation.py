"""
Module 13 — Actual Risk Reconciliation.
"""

import math
from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.transaction_cost import calculate_transaction_cost


class ActualRiskReconciliationModule(BaseRiskModule):
    """
    Module 13: Recalculates actual risks from scratch after executable sizing and cost calculations.

    Central Invariant Enforced:
        actual_total_risk = actual_stop_loss_risk + actual_transaction_cost <= permitted_risk_budget
    """

    @property
    def name(self) -> str:
        return "risk_reconciliation"

    @property
    def module_type(self) -> str:
        return "reconciliation"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "executable_position_size": state.executable_position_size,
            "permitted_risk_budget": state.permitted_risk_budget,
            "monetary_risk_per_unit": state.monetary_risk_per_unit,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "executable_position_size": state.executable_position_size,
            "actual_stop_loss_risk": state.actual_stop_loss_risk,
            "actual_transaction_cost": state.actual_transaction_cost,
            "actual_total_risk": state.actual_total_risk,
            "permitted_risk_budget": state.permitted_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        size = state.executable_position_size
        permitted = state.permitted_risk_budget
        risk_per_unit = state.monetary_risk_per_unit

        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)
        inst = state.instrument

        qty_inc = inst.quantity_increment
        min_qty = inst.min_quantity

        if size <= 0 or permitted <= 0:
            state.actual_stop_loss_risk = 0.0
            state.actual_transaction_cost = 0.0
            state.actual_total_risk = 0.0
            state.final_position_size = 0.0
            state.executable_position_size = 0.0
            state.final_risk = 0.0
            status = "REJECT"
            reason = "Zero position size or non-positive permitted risk budget"
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

        # Recalculate transaction costs from scratch for exact quantity
        _, _, _, actual_tx_cost = calculate_transaction_cost(state, size)
        actual_stop_risk = inst.calculate_loss_for_price_move(
            state.stop_distance, size, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
        ) if state.stop_distance > 0 else 0.0
        actual_total = actual_stop_risk + actual_tx_cost

        # Central Invariant Check: actual_total_risk <= permitted_risk_budget
        if actual_total > permitted + 1e-6:
            curr_size = size
            while curr_size >= min_qty:
                stop_risk = inst.calculate_loss_for_price_move(
                    state.stop_distance, curr_size, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
                ) if state.stop_distance > 0 else 0.0
                _, _, _, tx_cost = calculate_transaction_cost(state, curr_size)
                tot_risk = stop_risk + tx_cost
                if tot_risk <= permitted + 1e-6:
                    break
                next_size = curr_size - qty_inc
                if qty_inc >= 1.0:
                    curr_size = float(int(round(next_size)))
                else:
                    decimals = max(0, -int(math.floor(math.log10(qty_inc))))
                    curr_size = round(next_size, decimals)

            if curr_size < min_qty:
                state.add_rejection(
                    f"Actual total risk (${actual_total:,.2f}) exceeds permitted budget (${permitted:,.2f}). "
                    f"Stepping down position size drops below minimum quantity ({min_qty})"
                )
                size = 0.0
                actual_stop_risk = 0.0
                actual_tx_cost = 0.0
                actual_total = 0.0
                status = "REJECT"
                reason = "Reconciled actual total risk exceeded permitted budget and could not be stepped down above min_quantity"
            else:
                state.add_warning(
                    f"Actual total risk (${actual_total:,.2f}) exceeded permitted budget (${permitted:,.2f}); "
                    f"stepped down executable position size from {size} to {curr_size}"
                )
                size = curr_size
                actual_stop_risk = inst.calculate_loss_for_price_move(
                    state.stop_distance, size, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
                ) if state.stop_distance > 0 else 0.0
                _, _, _, actual_tx_cost = calculate_transaction_cost(state, size)
                actual_total = actual_stop_risk + actual_tx_cost
                status = "PASS"
                reason = f"Reconciled actual total risk (${actual_total:,.2f}) to permitted budget (${permitted:,.2f})"
        else:
            status = "PASS"
            reason = f"Reconciled actual total risk (${actual_total:,.2f}) <= permitted budget (${permitted:,.2f})"

        state.executable_position_size = size
        state.final_position_size = size
        state.actual_stop_loss_risk = actual_stop_risk
        state.actual_transaction_cost = actual_tx_cost
        state.actual_total_risk = actual_total
        state.final_risk = actual_total
        state.final_risk_pct = actual_total / state.account.equity if state.account.equity > 0 else 0.0

        msg = f"Reconciled Actual Total Risk = ${actual_total:,.2f} (Stop Risk = ${actual_stop_risk:,.2f}, Tx Cost = ${actual_tx_cost:,.2f}) <= Permitted = ${permitted:,.2f}, Size = {size}"
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
