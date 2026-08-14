"""
Module 13 — Actual Risk Reconciliation.
"""

import math
from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class ActualRiskReconciliationModule(BaseRiskModule):
    """
    Module 13: Recalculates actual risks from scratch after executable sizing and cost calculations.

    Central Invariant Enforced:
        actual_total_risk <= permitted_risk_budget
    """

    @property
    def name(self) -> str:
        return "risk_reconciliation"

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
            status = "PASS" if permitted == 0 else "REJECT"
            reason = "Zero position size or non-positive permitted risk budget"
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status=status,
                reason=reason,
            )
            return state

        # Unit total risk = risk_per_unit + tx_cost_per_unit
        tx_cost_per_unit = state.total_transaction_cost / size if size > 0 else 0.0
        unit_total_risk = risk_per_unit + tx_cost_per_unit

        actual_stop_risk = size * risk_per_unit
        actual_tx_cost = size * tx_cost_per_unit
        actual_total = actual_stop_risk + actual_tx_cost

        # Central Invariant Check: actual_total_risk <= permitted_risk_budget
        if actual_total > permitted + 1e-6:
            # Step down size until invariant holds
            max_safe_units = math.floor((permitted / unit_total_risk) / qty_inc) * qty_inc
            if qty_inc >= 1.0:
                max_safe_units = float(int(max_safe_units))
            else:
                decimals = max(0, -int(math.floor(math.log10(qty_inc))))
                max_safe_units = round(max_safe_units, decimals)

            if max_safe_units < min_qty:
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
                    f"stepped down executable position size from {size} to {max_safe_units}"
                )
                size = max_safe_units
                actual_stop_risk = size * risk_per_unit
                actual_tx_cost = size * tx_cost_per_unit
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
        state.final_risk = actual_stop_risk

        # Recalculate stress loss for final reconciled position size
        if inst is not None and size > 0:
            entry = state.trade.entry_price
            stress_limits = state.config.stress_limits
            gap_pct = stress_limits.get("gap_pct", 0.01)
            extra_slip_pct = stress_limits.get("extra_slippage_pct", 0.005)
            gap_loss = size * inst.contract_size * (entry * gap_pct)
            slip_loss = size * inst.contract_size * (entry * extra_slip_pct)
            state.stress_loss = actual_stop_risk + gap_loss + slip_loss
            state.stress_loss_pct = state.stress_loss / state.account.equity if state.account.equity > 0 else 0.0

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
