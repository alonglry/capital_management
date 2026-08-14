"""
Module 10 — Stress Test Capacity Constraint.
"""

from typing import Any, Dict, Tuple

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskConstraint
from capital_management.modules.quantity_solver import solve_max_executable_quantity
from capital_management.modules.transaction_cost import calculate_transaction_cost


class StressTestModule(RiskConstraint):
    """
    Module 10: Hard risk constraint evaluating position stress loss under adverse gap/slippage scenarios
    using quantity-based solve_max_executable_quantity solver.
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
            "stress_total_risk": state.stress_total_risk,
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

        if gap_pct < 0 or extra_slip_pct < 0:
            raise ValueError(f"Invalid stress parameters: gap_pct={gap_pct}, extra_slippage_pct={extra_slip_pct}")

        inst = state.instrument
        if inst is None:
            raise ValueError("Missing InstrumentSpec for stress calculation")

        acct_ccy = state.account.currency
        pip_val = state.trade.pip_value_per_lot
        pip_ccy = state.trade.pip_value_currency
        fx_rates = state.market_data.fx_rates

        extra_slip_dist = entry * extra_slip_pct
        gap_dist = entry * gap_pct

        if side == "long":
            stressed_exit_price = entry * (1.0 - gap_pct) - extra_slip_dist
            if stressed_exit_price <= 0:
                raise ValueError(f"Long stress exit price ({stressed_exit_price}) is non-positive.")
            stress_direction = "adverse_down"
        else:
            stressed_exit_price = entry * (1.0 + gap_pct) + extra_slip_dist
            stress_direction = "adverse_up"

        stressed_price_dist = abs(entry - stressed_exit_price)
        stressed_market_loss = inst.calculate_loss_for_price_move(
            price_move_distance=stressed_price_dist,
            quantity=q,
            account_currency=acct_ccy,
            entry_price=entry,
            pip_value_per_lot=pip_val,
            pip_value_currency=pip_ccy,
            fx_rates=fx_rates,
        )

        _, _, _, tx_cost = calculate_transaction_cost(state, q)
        stress_total_risk = stressed_market_loss + tx_cost

        normal_stop_risk = inst.calculate_loss_for_price_move(
            price_move_distance=state.stop_distance,
            quantity=q,
            account_currency=acct_ccy,
            entry_price=entry,
            pip_value_per_lot=pip_val,
            pip_value_currency=pip_ccy,
            fx_rates=fx_rates,
        ) if state.stop_distance > 0 else 0.0

        normal_total_risk = normal_stop_risk + tx_cost

        gap_loss = inst.calculate_loss_for_price_move(
            price_move_distance=gap_dist,
            quantity=q,
            account_currency=acct_ccy,
            entry_price=entry,
            pip_value_per_lot=pip_val,
            pip_value_currency=pip_ccy,
            fx_rates=fx_rates,
        )
        slip_loss = inst.calculate_loss_for_price_move(
            price_move_distance=extra_slip_dist,
            quantity=q,
            account_currency=acct_ccy,
            entry_price=entry,
            pip_value_per_lot=pip_val,
            pip_value_currency=pip_ccy,
            fx_rates=fx_rates,
        )

        return normal_stop_risk, tx_cost, normal_total_risk, gap_loss, slip_loss, stress_total_risk, stress_direction, stressed_exit_price

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.risk_equity_snapshot
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

        if state.monetary_risk_per_unit <= 0 or state.instrument is None:
            state.stress_risk_capacity = 0.0
            state.permitted_risk_budget = 0.0
            state.add_rejection("Invalid monetary risk per unit or missing InstrumentSpec in StressTestModule.")
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Invalid monetary risk per unit or missing InstrumentSpec",
            )
            return state

        inst = state.instrument
        qty_inc = inst.quantity_increment or 1.0
        min_qty = inst.min_quantity or 1.0
        max_qty = inst.max_quantity or 100000.0

        # Define quantity-based stress risk function for solver
        def stress_risk_fn(q: float) -> float:
            _, _, _, _, _, stress_t, _, _ = self._calculate_stress_loss_for_quantity(q, state)
            return stress_t

        q_stress_max, is_satisfied = solve_max_executable_quantity(
            stress_risk_fn, max_stress_monetary, min_qty, max_qty, qty_inc
        )

        if is_satisfied and q_stress_max > 0:
            stress_capacity = inst.calculate_loss_for_price_move(
                price_move_distance=state.stop_distance,
                quantity=q_stress_max,
                account_currency=state.account.currency,
                entry_price=state.trade.entry_price,
                pip_value_per_lot=state.trade.pip_value_per_lot,
                pip_value_currency=state.trade.pip_value_currency,
                fx_rates=state.market_data.fx_rates,
            ) if state.stop_distance > 0 else q_stress_max * state.monetary_risk_per_unit
        else:
            stress_capacity = 0.0

        state.stress_risk_capacity = stress_capacity
        prev_permitted = state.permitted_risk_budget
        new_permitted = min(prev_permitted, stress_capacity)
        state.permitted_risk_budget = new_permitted

        # Check existing executable position size if provided
        specified_size = state.executable_position_size
        if specified_size > 0:
            stop_r, tx_c, norm_t, gap_l, slip_l, stress_t, stress_dir, stressed_exit = self._calculate_stress_loss_for_quantity(specified_size, state)
        else:
            est_q = q_stress_max
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
