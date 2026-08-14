"""
Module 14 — Final Risk Validation.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class FinalValidationModule(BaseRiskModule):
    """
    Module 14: Final risk validation gate enforcing 17 explicit safety conditions.
    """

    @property
    def name(self) -> str:
        return "final_validation"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "final_position_size": state.final_position_size,
            "actual_total_risk": state.actual_total_risk,
            "permitted_risk_budget": state.permitted_risk_budget,
            "rejection_reasons": list(state.rejection_reasons),
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "approved": state.approved,
            "actual_total_risk": state.actual_total_risk,
            "permitted_risk_budget": state.permitted_risk_budget,
            "rejection_reasons": list(state.rejection_reasons),
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        size = state.final_position_size
        entry = state.trade.entry_price
        stop = state.trade.proposed_stop_price
        stop_dist = state.stop_distance
        inst = state.instrument

        # 1. Entry price valid
        if entry <= 0 or math.isnan(entry) or math.isinf(entry):
            state.add_rejection(f"Invalid entry price ({entry})")

        # 2. Stop price valid
        if stop <= 0 or math.isnan(stop) or math.isinf(stop):
            state.add_rejection(f"Invalid stop price ({stop})")

        # 3. Stop distance > 0
        if stop_dist <= 0 or math.isnan(stop_dist) or math.isinf(stop_dist):
            state.add_rejection(f"Invalid stop distance ({stop_dist}). Must be > 0.")

        # 4. Position quantity > 0
        if size <= 0:
            state.add_rejection(f"Position quantity ({size}) is zero or negative.")

        # 5 & 6. Quantity respects increment, min, max
        if inst is not None:
            if size < inst.min_quantity - 1e-6:
                state.add_rejection(f"Position quantity ({size}) is below minimum allowed ({inst.min_quantity})")
            if size > inst.max_quantity + 1e-6:
                state.add_rejection(f"Position quantity ({size}) exceeds maximum allowed ({inst.max_quantity})")
            inc_rem = abs(size / inst.quantity_increment - round(size / inst.quantity_increment))
            if inc_rem > 1e-4:
                state.add_rejection(f"Position quantity ({size}) does not respect quantity increment ({inst.quantity_increment})")

        # 7. Actual stop-loss risk <= permitted risk
        if state.actual_stop_loss_risk > state.permitted_risk_budget + 1e-4:
            state.add_rejection(
                f"Actual stop-loss risk (${state.actual_stop_loss_risk:,.2f}) exceeds permitted risk budget (${state.permitted_risk_budget:,.2f})"
            )

        # 8. Transaction cost valid
        if state.actual_transaction_cost < 0 or math.isnan(state.actual_transaction_cost) or math.isinf(state.actual_transaction_cost):
            state.add_rejection(f"Invalid transaction cost (${state.actual_transaction_cost})")

        # 9. CENTRAL INVARIANT: Actual total risk <= permitted risk budget
        if state.actual_total_risk > state.permitted_risk_budget + 1e-4:
            state.add_rejection(
                f"CENTRAL INVARIANT VIOLATION: Actual total risk (${state.actual_total_risk:,.2f}) exceeds permitted risk budget (${state.permitted_risk_budget:,.2f})"
            )

        # 10. Portfolio heat remains within limit
        if state.projected_portfolio_heat > state.config.max_portfolio_heat_pct + 1e-6:
            state.add_rejection(
                f"Projected portfolio heat ({state.projected_portfolio_heat:.2%}) exceeds maximum limit ({state.config.max_portfolio_heat_pct:.2%})"
            )

        # 11. Correlation risk remains within limit
        if state.projected_correlation_adjusted_risk > state.config.max_correlation_adjusted_risk_pct + 1e-6:
            state.add_rejection(
                f"Projected correlation risk ({state.projected_correlation_adjusted_risk:.2%}) exceeds maximum limit ({state.config.max_correlation_adjusted_risk_pct:.2%})"
            )

        # 12. Factor exposure remains within limit
        if state.factor_constraint_status == "REJECT":
            state.add_rejection("Factor exposure limit violation detected.")

        # 13. Stress risk remains within limit
        max_stress_loss = equity * state.config.stress_limits.get("max_stress_risk_pct", 0.02) if equity > 0 else 0.0
        if state.stress_loss > max_stress_loss + 1e-4:
            state.add_rejection(
                f"Stress loss (${state.stress_loss:,.2f}) exceeds maximum stress limit (${max_stress_loss:,.2f})"
            )

        # 14. Instrument metadata exists
        if inst is None:
            state.add_rejection("Missing required InstrumentSpec metadata.")

        # 15. No NaN / Infinity in key metrics
        for name, val in [
            ("actual_total_risk", state.actual_total_risk),
            ("permitted_risk_budget", state.permitted_risk_budget),
            ("final_position_size", state.final_position_size),
        ]:
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                state.add_rejection(f"Invalid numeric value ({val}) for {name}")

        # 16. No negative risk
        if state.actual_total_risk < 0:
            state.add_rejection(f"Negative actual total risk ({state.actual_total_risk})")

        # 17. No negative quantity
        if size < 0:
            state.add_rejection(f"Negative position quantity ({size})")

        # Set final approval boolean
        state.approved = (len(state.rejection_reasons) == 0)

        status = "PASS" if state.approved else "REJECT"
        if state.approved:
            reason = f"Trade APPROVED: Executable size = {size:,.4f}, Actual total risk = ${state.actual_total_risk:,.2f} <= Permitted budget = ${state.permitted_risk_budget:,.2f}"
        else:
            reason = f"Trade REJECTED due to {len(state.rejection_reasons)} safety gate violation(s)."

        msg = f"Approved = {state.approved}, Executable Size = {size:,.4f}, Actual Risk = ${state.actual_total_risk:,.2f}, Permitted = ${state.permitted_risk_budget:,.2f}, Status = {status}"
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
