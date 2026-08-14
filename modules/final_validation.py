"""
Module 12 — Final Risk Validation.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class FinalValidationModule(BaseRiskModule):
    """
    Module 12: Final risk validation gate that enforces all 8 risk constraints and determines approval.

    Enforces:
    1. position size > 0
    2. individual risk <= max trade risk
    3. portfolio heat <= max portfolio heat
    4. correlation risk <= correlation limit
    5. factor exposure <= factor limits
    6. stress loss <= stress limit
    7. transaction costs acceptable
    8. instrument constraints satisfied
    """

    @property
    def name(self) -> str:
        return "final_validation"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "final_position_size": state.final_position_size,
            "rejection_reasons": list(state.rejection_reasons),
            "max_trade_risk_pct": state.config.max_trade_risk_pct,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "approved": state.approved,
            "final_risk": state.final_risk,
            "final_risk_pct": state.final_risk_pct,
            "rejection_reasons": list(state.rejection_reasons),
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        size = state.final_position_size
        stop_dist = state.stop_distance

        # Calculate final monetary risk
        if state.trade.asset_class.lower() == "forex" and state.trade.pip_value_per_lot:
            pip_val = state.trade.pip_value_per_lot
            pip_size = 0.01 if "JPY" in state.trade.symbol.upper() else 0.0001
            pips = stop_dist / pip_size
            final_risk = size * (pips * pip_val)
        else:
            point_val = state.trade.point_value or 1.0
            final_risk = size * stop_dist * point_val

        final_risk_pct = final_risk / equity if equity > 0 else 0.0

        state.final_risk = final_risk
        state.final_risk_pct = final_risk_pct

        # 1. Check position size > 0
        if size <= 0:
            state.add_rejection(f"Final position size ({size}) is zero or negative.")

        # 2. Check individual risk <= max trade risk
        max_trade_risk_monetary = equity * state.config.max_trade_risk_pct
        if final_risk > max_trade_risk_monetary + 1e-6:
            state.add_rejection(
                f"Final individual trade risk (${final_risk:,.2f}, {final_risk_pct:.2%}) exceeds max trade risk limit (${max_trade_risk_monetary:,.2f}, {state.config.max_trade_risk_pct:.2%})"
            )

        # 3. Portfolio heat check
        if state.projected_portfolio_heat > state.config.max_portfolio_heat_pct + 1e-6:
            state.add_rejection(
                f"Projected portfolio heat ({state.projected_portfolio_heat:.2%}) exceeds maximum limit ({state.config.max_portfolio_heat_pct:.2%})"
            )

        # 4. Correlation risk check
        if state.projected_correlation_adjusted_risk > state.config.max_correlation_adjusted_risk_pct + 1e-6:
            state.add_rejection(
                f"Projected correlation-adjusted risk ({state.projected_correlation_adjusted_risk:.2%}) exceeds maximum limit ({state.config.max_correlation_adjusted_risk_pct:.2%})"
            )

        # 5. Factor exposure check
        if state.factor_constraint_status == "REJECT":
            state.add_rejection("Factor exposure limit violation detected.")

        # 6. Stress loss check
        max_stress_loss = equity * state.config.stress_limits.get("max_stress_risk_pct", 0.02)
        if state.stress_loss > max_stress_loss + 1e-6:
            state.add_rejection(
                f"Stress loss (${state.stress_loss:,.2f}, {state.stress_loss_pct:.2%}) exceeds stress limit (${max_stress_loss:,.2f})"
            )

        # 7. Transaction cost check
        if state.total_transaction_cost > state.base_risk_budget and state.base_risk_budget > 0:
            state.add_rejection(
                f"Total transaction cost (${state.total_transaction_cost:,.2f}) exceeds initial risk budget (${state.base_risk_budget:,.2f})"
            )

        # 8. Instrument constraints check
        if stop_dist <= 0:
            state.add_rejection(f"Invalid stop distance ({stop_dist}). Must be > 0.")

        # Set final approval
        state.approved = (len(state.rejection_reasons) == 0)

        status = "PASS" if state.approved else "REJECT"
        if state.approved:
            reason = f"Trade APPROVED: Final position size = {size:,.4f}, Final risk = ${final_risk:,.2f} ({final_risk_pct:.2%})"
        else:
            reason = f"Trade REJECTED due to {len(state.rejection_reasons)} constraint violation(s)."

        msg = f"Approved = {state.approved}, Final Size = {size:,.4f}, Final Risk = ${final_risk:,.2f} ({final_risk_pct:.2%}), Status = {status}"
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
