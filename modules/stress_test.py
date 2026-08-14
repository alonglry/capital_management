"""
Module 11 — Stress Test.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.position_sizing import PositionSizingModule


class StressTestModule(BaseRiskModule):
    """
    Module 11: Stresses proposed position against adverse gap and slippage scenarios.

    Formula:
        Normal Loss = position_size * stop_distance
        Gap Loss = position_size * (entry_price * gap_pct)
        Slippage Loss = position_size * (entry_price * extra_slippage_pct)
        Stress Loss = Normal Loss + Gap Loss + Slippage Loss
    """

    @property
    def name(self) -> str:
        return "stress_test"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "position_size": state.final_position_size,
            "equity": state.account.equity,
            "stress_limits": state.config.stress_limits,
            "stress_policy": state.config.stress_policy,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "normal_loss": state.normal_loss,
            "stress_loss": state.stress_loss,
            "stress_loss_pct": state.stress_loss_pct,
            "final_position_size": state.final_position_size,
        }

    def _calculate_losses(self, size: float, state: CapitalManagementState) -> tuple[float, float]:
        entry = state.trade.entry_price
        stop_dist = state.stop_distance
        stress_limits = state.config.stress_limits

        gap_pct = stress_limits.get("gap_pct", 0.01)
        extra_slip_pct = stress_limits.get("extra_slippage_pct", 0.005)

        asset_class = state.trade.asset_class.lower()

        if asset_class == "forex" and state.trade.pip_value_per_lot:
            pip_val = state.trade.pip_value_per_lot
            pip_size = 0.01 if "JPY" in state.trade.symbol.upper() else 0.0001
            pips = stop_dist / pip_size
            normal_loss = size * (pips * pip_val)
            lot_units = 100000.0 if state.trade.lot_size is None else state.trade.lot_size
            gap_loss = size * lot_units * (entry * gap_pct)
            slip_loss = size * lot_units * (entry * extra_slip_pct)
        else:
            point_val = state.trade.point_value or 1.0
            normal_loss = size * stop_dist * point_val
            gap_loss = size * (entry * gap_pct)
            slip_loss = size * (entry * extra_slip_pct)

        stress_loss = normal_loss + gap_loss + slip_loss
        return normal_loss, stress_loss

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        size = state.final_position_size

        if equity <= 0 or size <= 0:
            state.normal_loss = 0.0
            state.stress_loss = 0.0
            state.stress_loss_pct = 0.0
            status = "PASS"
            reason = "Zero position size or equity, stress test skipped"
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status=status,
                reason=reason,
            )
            return state

        normal_loss, stress_loss = self._calculate_losses(size, state)
        stress_loss_pct = stress_loss / equity

        state.normal_loss = normal_loss
        state.stress_loss = stress_loss
        state.stress_loss_pct = stress_loss_pct

        limits = state.config.stress_limits
        max_stress_risk_pct = limits.get("max_stress_risk_pct", 0.02)
        max_stress_loss = equity * max_stress_risk_pct

        status = "PASS"
        reason = f"Stress loss ${stress_loss:,.2f} ({stress_loss_pct:.2%}) <= limit ${max_stress_loss:,.2f} ({max_stress_risk_pct:.2%})"

        if stress_loss > max_stress_loss:
            if state.config.stress_policy == "reject":
                status = "REJECT"
                reason = f"Stress loss ${stress_loss:,.2f} ({stress_loss_pct:.2%}) exceeds limit ${max_stress_loss:,.2f} ({max_stress_risk_pct:.2%})"
                state.add_rejection(reason)
            else:  # 'reduce'
                # Scale down position size
                scale = max_stress_loss / stress_loss if stress_loss > 0 else 0.0
                raw_reduced = size * scale
                sizer = PositionSizingModule()
                reduced_size = sizer._apply_rounding(raw_reduced, state.trade.asset_class, state)
                state.final_position_size = reduced_size

                normal_loss, stress_loss = self._calculate_losses(reduced_size, state)
                stress_loss_pct = stress_loss / equity
                state.normal_loss = normal_loss
                state.stress_loss = stress_loss
                state.stress_loss_pct = stress_loss_pct

                state.add_warning(
                    f"Reduced position size from {size} to {reduced_size} to meet stress loss cap (${max_stress_loss:,.2f})"
                )
                status = "PASS"
                reason = f"Position size reduced to {reduced_size} to keep stress loss at ${stress_loss:,.2f}"

        msg = f"Normal Loss = ${normal_loss:,.2f}, Stress Loss = ${stress_loss:,.2f} ({stress_loss_pct:.2%}), Limit = ${max_stress_loss:,.2f}, Status = {status}"
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
