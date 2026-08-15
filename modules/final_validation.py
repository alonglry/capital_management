"""
Module 14 — Final Risk Validation.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class FinalValidationModule(BaseRiskModule):
    """
    Module 14: Final risk validation gate enforcing explicit safety conditions, finite numbers, ledgers, and idempotency.
    """

    @property
    def name(self) -> str:
        return "final_validation"

    @property
    def module_type(self) -> str:
        return "validation"

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
            "binding_constraints": list(state.binding_constraints),
            "risk_ledger": state.risk_ledger.to_dict(),
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.risk_equity_snapshot
        size = state.final_position_size
        entry = state.trade.entry_price
        stop = state.effective_stop_price if state.effective_stop_price is not None else state.trade.proposed_stop_price
        stop_dist = state.stop_distance
        inst = state.instrument

        # Determine binding constraints
        binding: list = []
        p_budget = state.permitted_risk_budget
        tol = 1e-4

        if abs(state.trade_risk_capacity - p_budget) <= tol:
            binding.append("trade_risk_capacity")
        if abs(state.portfolio_heat_capacity - p_budget) <= tol:
            binding.append("portfolio_heat")
        if abs(state.correlation_risk_capacity - p_budget) <= tol:
            binding.append("correlation")
        if abs(state.factor_risk_capacity - p_budget) <= tol:
            binding.append("factor")
        if abs(state.stress_risk_capacity - p_budget) <= tol:
            binding.append("stress")
        if not binding:
            binding.append("governed_risk_budget")

        state.binding_constraints = binding

        # Check prior module rejections to ensure terminal rejection propagation
        for m_name, m_res in state.module_results.items():
            if m_name != self.name and m_res.status in ("REJECT", "FAIL"):
                err_msg = f"Upstream hard rejection in module '{m_name}': {m_res.reason}"
                if err_msg not in state.rejection_reasons:
                    state.add_rejection(err_msg)

        # 1. Equity > 0 required
        if equity <= 0 or not math.isfinite(equity):
            state.add_rejection(f"Account equity snapshot ({equity}) is non-positive or non-finite.")

        # 2. Stop direction check
        valid_dir, msg_dir = state.trade.validate_stop_direction(stop_price=stop)
        if not valid_dir:
            state.add_rejection(f"Stop direction validation failed: {msg_dir}")

        # 3. Instrument Spec existence & symbol/asset_class consistency
        if inst is None:
            state.add_rejection("Missing required explicit InstrumentSpec metadata.")
        else:
            if inst.symbol.upper() != state.trade.symbol.upper():
                state.add_rejection(f"Symbol mismatch: trade ({state.trade.symbol}) vs instrument ({inst.symbol})")
            if inst.asset_class.upper() != state.trade.asset_class.upper():
                state.add_rejection(f"Asset class mismatch: trade ({state.trade.asset_class}) vs instrument ({inst.asset_class})")

            # Production metadata verification requirement check
            if state.config.require_verified_instrument_metadata == "reject" and not inst.metadata_verified:
                state.add_rejection("Unsafe InstrumentSpec default metadata in production mode.")

        # 4. Entry price valid
        if entry <= 0 or not math.isfinite(entry):
            state.add_rejection(f"Invalid entry price ({entry})")

        # 5. Stop price valid
        if stop <= 0 or not math.isfinite(stop):
            state.add_rejection(f"Invalid stop price ({stop})")

        # 6. Stop distance > 0
        if stop_dist <= 0 or not math.isfinite(stop_dist):
            state.add_rejection(f"Invalid stop distance ({stop_dist}). Must be > 0.")

        # 7. Position quantity > 0
        if size <= 0:
            state.add_rejection(f"Position quantity ({size}) is zero or negative.")

        # 8 & 9. Quantity respects increment, min, max
        if inst is not None:
            min_q = inst.min_quantity or 0.01
            max_q = inst.max_quantity or 100000.0
            inc_q = inst.quantity_increment or 0.01
            if size > 0 and size < min_q - 1e-6:
                state.add_rejection(f"Position quantity ({size}) is below minimum allowed ({min_q})")
            if size > max_q + 1e-6:
                state.add_rejection(f"Position quantity ({size}) exceeds maximum allowed ({max_q})")
            if size > 0:
                inc_rem = abs(size / inc_q - round(size / inc_q))
                if inc_rem > 1e-4:
                    state.add_rejection(f"Position quantity ({size}) does not respect quantity increment ({inc_q})")

        # 10. Monetary risk per unit > 0
        if state.monetary_risk_per_unit <= 0 or not math.isfinite(state.monetary_risk_per_unit):
            state.add_rejection(f"Monetary risk per unit ({state.monetary_risk_per_unit}) must be > 0.")

        # 11. CENTRAL INVARIANT: Actual total risk <= permitted risk budget
        if state.actual_total_risk > state.permitted_risk_budget + 1e-4:
            state.add_rejection(
                f"CENTRAL INVARIANT VIOLATION: Actual total risk (${state.actual_total_risk:,.2f}) exceeds permitted risk budget (${state.permitted_risk_budget:,.2f})"
            )

        # 12. Portfolio heat remains within limit
        if state.projected_portfolio_heat > state.config.max_portfolio_heat_pct + 1e-6:
            state.add_rejection(
                f"Projected portfolio heat ({state.projected_portfolio_heat:.2%}) exceeds maximum limit ({state.config.max_portfolio_heat_pct:.2%})"
            )

        # 13. Correlation risk remains within limit
        if state.projected_correlation_adjusted_risk > state.config.max_correlation_adjusted_risk_pct + 1e-6:
            state.add_rejection(
                f"Projected correlation risk ({state.projected_correlation_adjusted_risk:.2%}) exceeds maximum limit ({state.config.max_correlation_adjusted_risk_pct:.2%})"
            )

        # 14. Factor exposure remains within limit
        if state.factor_constraint_status == "REJECT":
            state.add_rejection("Factor exposure limit violation detected.")

        # 15. Stress total risk remains within limit
        max_stress_loss = equity * state.config.stress_limits.get("max_stress_risk_pct", 0.02) if equity > 0 else 0.0
        if state.stress_total_risk > max_stress_loss + 1e-4:
            state.add_rejection(
                f"Stress total risk (${state.stress_total_risk:,.2f}) exceeds maximum stress limit (${max_stress_loss:,.2f})"
            )

        # 16. Generic finite-value validation over all key numeric state fields
        numeric_fields = {
            "account.equity": equity,
            "permitted_risk_budget": state.permitted_risk_budget,
            "base_risk_budget": state.base_risk_budget,
            "requested_risk_budget": state.requested_risk_budget,
            "governed_risk_budget": state.governed_risk_budget,
            "trade_risk_capacity": state.trade_risk_capacity,
            "portfolio_heat_capacity": state.portfolio_heat_capacity,
            "correlation_risk_capacity": state.correlation_risk_capacity,
            "factor_risk_capacity": state.factor_risk_capacity,
            "stress_risk_capacity": state.stress_risk_capacity,
            "stop_distance": state.stop_distance,
            "monetary_risk_per_unit": state.monetary_risk_per_unit,
            "final_position_size": state.final_position_size,
            "actual_stop_loss_risk": state.actual_stop_loss_risk,
            "actual_transaction_cost": state.actual_transaction_cost,
            "actual_total_risk": state.actual_total_risk,
            "stress_loss": state.stress_loss,
            "stress_total_risk": state.stress_total_risk,
        }
        for name, val in numeric_fields.items():
            if not isinstance(val, (int, float)) or math.isnan(val):
                state.add_rejection(f"Invalid non-finite or NaN numeric value ({val}) for {name}")
            elif "capacity" not in name and not math.isfinite(val):
                state.add_rejection(f"Invalid non-finite numeric value ({val}) for {name}")

        # Set final approval boolean
        state.approved = (len(state.rejection_reasons) == 0)

        # Preserve attempted risk ledger diagnostics, but set final_position_size = 0.0 if not approved
        if not state.approved:
            state.final_position_size = 0.0

        status = "PASS" if state.approved else "REJECT"
        if state.approved:
            reason = f"Trade APPROVED: Executable size = {size:,.4f}, Actual total risk = ${state.actual_total_risk:,.2f} <= Permitted budget = ${state.permitted_risk_budget:,.2f}"
        else:
            reason = f"Trade REJECTED due to {len(state.rejection_reasons)} safety gate violation(s)."

        msg = f"Approved = {state.approved}, Executable Size = {state.final_position_size:,.4f}, Actual Risk = ${state.actual_total_risk:,.2f}, Permitted = ${state.permitted_risk_budget:,.2f}, Status = {status}"
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
