"""
Module 12 — Stress Test.
"""

from typing import Any, Dict, Tuple

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskConstraint


class StressTestModule(RiskConstraint):
    """
    Module 12: Hard risk constraint evaluating position stress loss under adverse gap/slippage scenarios
    and computing stress_risk_capacity.
    """

    @property
    def name(self) -> str:
        return "stress_test"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "executable_position_size": state.executable_position_size,
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
        }

    def _calculate_losses(self, size: float, state: CapitalManagementState) -> Tuple[float, float, float]:
        entry = state.trade.entry_price
        stop_dist = state.stop_distance
        stress_limits = state.config.stress_limits

        gap_pct = stress_limits.get("gap_pct", 0.01)
        extra_slip_pct = stress_limits.get("extra_slippage_pct", 0.005)

        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)
        inst = state.instrument

        normal_loss = size * state.monetary_risk_per_unit
        gap_loss = size * inst.contract_size * (entry * gap_pct)
        slip_loss = size * inst.contract_size * (entry * extra_slip_pct)

        stress_loss_total = normal_loss + gap_loss + slip_loss
        stress_loss_per_unit = state.monetary_risk_per_unit + (inst.contract_size * entry * (gap_pct + extra_slip_pct))
        return normal_loss, stress_loss_total, stress_loss_per_unit

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        size = state.executable_position_size
        limits = state.config.stress_limits
        max_stress_risk_pct = limits.get("max_stress_risk_pct", 0.02)
        max_stress_monetary = equity * max_stress_risk_pct

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

        normal_loss, stress_loss, stress_loss_per_unit = self._calculate_losses(size, state)
        stress_loss_pct = stress_loss / equity if equity > 0 else 0.0

        state.normal_loss = normal_loss
        state.stress_loss = stress_loss
        state.stress_loss_pct = stress_loss_pct

        # Compute stress capacity
        if stress_loss_per_unit > 0:
            max_stress_units = max_stress_monetary / stress_loss_per_unit
            stress_capacity = max_stress_units * state.monetary_risk_per_unit
        else:
            stress_capacity = state.permitted_risk_budget

        state.stress_risk_capacity = stress_capacity

        prev_permitted = state.permitted_risk_budget
        new_permitted = min(prev_permitted, stress_capacity)
        state.permitted_risk_budget = new_permitted

        policy = state.config.stress_policy.lower()
        if stress_capacity <= 0 or (policy == "reject" and stress_loss > max_stress_monetary + 1e-4):
            status = "REJECT"
            reason = f"Stress loss (${stress_loss:,.2f}) exceeds maximum stress limit (${max_stress_monetary:,.2f})"
            state.add_rejection(reason)
            state.stress_risk_capacity = 0.0
            state.permitted_risk_budget = 0.0
        elif new_permitted < prev_permitted:
            status = "PASS"
            reason = f"Stress capacity (${stress_capacity:,.2f}) constrained permitted risk from ${prev_permitted:,.2f} to ${new_permitted:,.2f}"
            state.add_warning(reason)
        else:
            status = "PASS"
            reason = f"Stress loss (${stress_loss:,.2f}) satisfies max stress limit (${max_stress_monetary:,.2f})"

        msg = f"Normal Loss = ${normal_loss:,.2f}, Stress Loss = ${stress_loss:,.2f} ({stress_loss_pct:.2%}), Capacity = ${stress_capacity:,.2f}, Status = {status}"
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
