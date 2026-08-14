"""
Module 10 — Stress Test Capacity Constraint.
"""

from typing import Any, Dict, Tuple

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskConstraint
from capital_management.modules.transaction_cost import calculate_transaction_cost


class StressTestModule(RiskConstraint):
    """
    Module 10: Hard risk constraint evaluating position stress loss under adverse gap/slippage scenarios
    and computing pre-sizing stress_risk_capacity as well as post-sizing validation.
    """

    @property
    def name(self) -> str:
        return "stress_test"

    @property
    def module_type(self) -> str:
        return "constraint"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "symbol": state.trade.symbol,
            "side": state.trade.side,
            "equity": state.account.equity,
            "stress_limits": state.config.stress_limits,
            "stress_policy": state.config.stress_policy,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "normal_loss": state.normal_loss,
            "stress_loss": state.stress_loss,
            "stress_loss_pct": state.stress_loss_pct,
            "stress_risk_capacity": state.stress_risk_capacity,
            "permitted_risk_budget": state.permitted_risk_budget,
            "stress_direction": getattr(state, "stress_direction", "adverse_down"),
            "stressed_exit_price": getattr(state, "stressed_exit_price", 0.0),
        }

    def _calculate_stress_loss_for_quantity(
        self, q: float, state: CapitalManagementState
    ) -> Tuple[float, float, float, float, float, float, str, float]:
        entry = state.trade.entry_price
        side = state.trade.side.lower()
        limits = state.config.stress_limits

        gap_pct = limits.get("gap_pct", 0.01)
        extra_slip_pct = limits.get("extra_slippage_pct", 0.005)

        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)
        inst = state.instrument

        acct_ccy = state.account.currency
        pip_val = state.trade.pip_value_per_lot
        pip_ccy = state.trade.pip_value_currency
        fx_rates = state.market_data.fx_rates

        # Side-aware exit price
        extra_slip_dist = entry * extra_slip_pct
        gap_dist = entry * gap_pct

        if side == "long":
            stressed_exit_price = entry * (1.0 - gap_pct) - extra_slip_dist
            stress_direction = "adverse_down"
        else:
            stressed_exit_price = entry * (1.0 + gap_pct) + extra_slip_dist
            stress_direction = "adverse_up"

        # 1. Normal risk components
        stop_risk = inst.calculate_loss_for_price_move(
            state.stop_distance, q, acct_ccy, entry, pip_val, pip_ccy, fx_rates
        ) if state.stop_distance > 0 else 0.0

        _, _, _, tx_cost = calculate_transaction_cost(state, q)
        normal_total_risk = stop_risk + tx_cost

        # 2. Incremental stress components
        gap_loss = inst.calculate_loss_for_price_move(
            gap_dist, q, acct_ccy, entry, pip_val, pip_ccy, fx_rates
        )
        slip_loss = inst.calculate_loss_for_price_move(
            extra_slip_dist, q, acct_ccy, entry, pip_val, pip_ccy, fx_rates
        )
        incremental_stress_loss = gap_loss + slip_loss

        stress_total_risk = normal_total_risk + incremental_stress_loss
        return stop_risk, tx_cost, normal_total_risk, gap_loss, slip_loss, stress_total_risk, stress_direction, stressed_exit_price

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        limits = state.config.stress_limits
        max_stress_risk_pct = limits.get("max_stress_risk_pct", 0.02)
        max_stress_monetary = equity * max_stress_risk_pct
        policy = state.config.stress_policy.lower()

        if equity <= 0:
            state.stress_risk_capacity = 0.0
            state.permitted_risk_budget = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Account equity is non-positive",
            )
            return state

        if state.monetary_risk_per_unit <= 0:
            state.stress_risk_capacity = state.permitted_risk_budget
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="PASS",
                reason="Monetary risk per unit not initialized",
            )
            return state

        # Compute unit stress loss for 1.0 unit
        stop_r1, tx1, norm1, gap1, slip1, stress1, stress_dir, stressed_exit = self._calculate_stress_loss_for_quantity(1.0, state)

        if stress1 > 0:
            max_stress_q = max_stress_monetary / stress1
            stress_capacity = max_stress_q * state.monetary_risk_per_unit
        else:
            stress_capacity = state.permitted_risk_budget

        state.stress_risk_capacity = stress_capacity
        prev_permitted = state.permitted_risk_budget
        new_permitted = min(prev_permitted, stress_capacity)
        state.permitted_risk_budget = new_permitted

        # Check if an explicit position size is already specified (post-sizing or manual input)
        specified_size = max(state.executable_position_size, state.final_position_size)
        if specified_size > 0:
            stop_r, tx_c, norm_t, gap_l, slip_l, stress_t, stress_dir, stressed_exit = self._calculate_stress_loss_for_quantity(specified_size, state)
        else:
            est_q = new_permitted / state.monetary_risk_per_unit if state.monetary_risk_per_unit > 0 else 0.0
            stop_r, tx_c, norm_t, gap_l, slip_l, stress_t, stress_dir, stressed_exit = self._calculate_stress_loss_for_quantity(est_q, state)

        state.normal_stop_loss_risk = stop_r
        state.normal_transaction_cost = tx_c
        state.normal_total_risk = norm_t
        state.normal_loss = norm_t
        state.incremental_gap_loss = gap_l
        state.incremental_stress_slippage_loss = slip_l
        state.stress_total_risk = stress_t
        state.stress_loss = stress_t
        state.stress_loss_pct = stress_t / equity if equity > 0 else 0.0
        state.stress_direction = stress_dir
        state.stressed_exit_price = stressed_exit

        if stress_capacity <= 0 or (specified_size > 0 and policy == "reject" and stress_t > max_stress_monetary + 1e-4):
            status = "REJECT"
            reason = f"Stress loss (${stress_t:,.2f}) exceeds maximum stress limit (${max_stress_monetary:,.2f})"
            state.add_rejection(reason)
            state.stress_risk_capacity = 0.0
            state.permitted_risk_budget = 0.0
        elif new_permitted < prev_permitted:
            status = "PASS"
            reason = f"Stress capacity (${stress_capacity:,.2f}) constrained permitted risk from ${prev_permitted:,.2f} to ${new_permitted:,.2f}"
            state.add_warning(reason)
        else:
            status = "PASS"
            reason = f"Stress loss (${stress_t:,.2f}) satisfies max stress limit (${max_stress_monetary:,.2f})"

        msg = f"Normal Loss = ${norm_t:,.2f}, Stress Loss = ${stress_t:,.2f}, Capacity = ${stress_capacity:,.2f}, Status = {status}"
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
