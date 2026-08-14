"""
Module 13 — Actual Risk Reconciliation.
"""

from typing import Any, Dict

from capital_management.models.ledger import RiskLedger
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.quantity_solver import solve_max_executable_quantity
from capital_management.modules.transaction_cost import calculate_transaction_cost


class ActualRiskReconciliationModule(BaseRiskModule):
    """
    Module 13: Recalculates actual risks from scratch after executable sizing and cost calculations
    using the canonical solve_max_executable_quantity solver, updating all cost fields and post-sizing metrics.
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

        qty_inc = inst.quantity_increment or 1.0
        min_qty = inst.min_quantity or 1.0
        max_qty = inst.max_quantity or 100000.0

        if size <= 0 or permitted <= 0:
            state.actual_stop_loss_risk = 0.0
            state.actual_transaction_cost = 0.0
            state.actual_total_risk = 0.0
            state.final_position_size = 0.0
            state.executable_position_size = 0.0
            state.final_risk = 0.0
            state.final_risk_pct = 0.0
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

        # Risk function for exact quantity
        def total_risk_fn(q: float) -> float:
            stop_r = inst.calculate_loss_for_price_move(
                state.stop_distance, q, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
            ) if state.stop_distance > 0 else 0.0
            _, _, _, tx_c = calculate_transaction_cost(state, q)
            return stop_r + tx_c

        reconciled_size, is_satisfied = solve_max_executable_quantity(
            total_risk_fn, permitted, min_qty, size, qty_inc
        )

        if not is_satisfied or reconciled_size < min_qty:
            status = "REJECT"
            reason = f"Reconciled total risk exceeded permitted budget (${permitted:,.2f}) and could not be stepped down above min_quantity ({min_qty})"
            state.add_rejection(reason)
            state.executable_position_size = 0.0
            state.final_position_size = 0.0
            state.cost_adjusted_position_size = 0.0
            state.actual_stop_loss_risk = 0.0
            state.actual_transaction_cost = 0.0
            state.actual_total_risk = 0.0
            state.final_risk = 0.0
            state.final_risk_pct = 0.0
        else:
            if reconciled_size < size:
                state.add_warning(
                    f"Actual total risk exceeded permitted budget (${permitted:,.2f}); stepped down size from {size} to {reconciled_size}"
                )

            size = reconciled_size
            spread_cost, comm_cost, slip_cost, actual_tx_cost = calculate_transaction_cost(state, size)
            actual_stop_risk = inst.calculate_loss_for_price_move(
                state.stop_distance, size, state.account.currency, state.trade.entry_price, state.trade.pip_value_per_lot, state.trade.pip_value_currency, state.market_data.fx_rates
            ) if state.stop_distance > 0 else 0.0
            actual_total = actual_stop_risk + actual_tx_cost

            # Synchronize ALL cost-related fields
            state.executable_position_size = size
            state.final_position_size = size
            state.cost_adjusted_position_size = size
            state.attempted_position_size = size
            state.estimated_spread_cost = spread_cost
            state.estimated_commission = comm_cost
            state.estimated_slippage = slip_cost
            state.total_transaction_cost = actual_tx_cost
            state.actual_stop_loss_risk = actual_stop_risk
            state.actual_transaction_cost = actual_tx_cost
            state.actual_total_risk = actual_total
            state.final_risk = actual_total
            state.final_risk_pct = actual_total / state.risk_equity_snapshot if state.risk_equity_snapshot > 0 else 0.0

            # Update formal RiskLedger
            state.risk_ledger = RiskLedger(
                stop_loss_risk=actual_stop_risk,
                transaction_cost=actual_tx_cost,
                financing_cost=state.financing_cost,
                short_borrow_cost=state.short_borrow_cost,
                normal_total_risk=actual_total,
                incremental_gap_loss=state.incremental_gap_loss,
                incremental_stress_slippage_loss=state.incremental_stress_slippage_loss,
                stress_total_risk=actual_total + state.incremental_gap_loss + state.incremental_stress_slippage_loss,
            )
            state.attempted_risk_ledger = state.risk_ledger

            # Post-reconciliation recomputation of quantity-dependent risk metrics
            eq = state.risk_equity_snapshot
            if eq > 0:
                state.projected_portfolio_heat = state.current_portfolio_heat + (actual_total / eq)

            status = "PASS"
            reason = f"Reconciled actual total risk (${actual_total:,.2f}) <= permitted budget (${permitted:,.2f})"

        msg = f"Reconciled Actual Total Risk = ${state.actual_total_risk:,.2f} (Stop = ${state.actual_stop_loss_risk:,.2f}, Cost = ${state.actual_transaction_cost:,.2f}) <= Permitted = ${permitted:,.2f}, Size = {state.final_position_size}"
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
