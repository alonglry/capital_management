"""
Module 1 — Base Risk Budget.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskTransformer


class BaseRiskBudgetModule(RiskTransformer):
    """
    Module 1: Calculates initial monetary risk budget.

    Formula:
        base_risk_budget = risk_capital_base * Base Risk %
    """

    @property
    def name(self) -> str:
        return "base_risk"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        equity = getattr(state.account, "equity", None) if state.account else None
        cash = getattr(state.account, "cash", None) if state.account else None
        return {
            "equity": equity,
            "cash": cash,
            "base_risk_pct": state.config.base_risk_pct,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "risk_capital_base": state.risk_capital_base,
            "risk_capital_source": state.risk_capital_source,
            "base_risk_budget": state.base_risk_budget,
            "governed_risk_budget": state.governed_risk_budget,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = getattr(state.account, "equity", None) if state.account else None
        cash = getattr(state.account, "cash", None) if state.account else None
        base_risk_pct = state.config.base_risk_pct

        risk_capital = None
        risk_capital_source = "unavailable"
        rejection_reason = None

        def is_valid_finite_number(val: Any) -> bool:
            return val is not None and isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val)

        # 1. Check if equity is a valid finite value > 0
        if is_valid_finite_number(equity):
            eq_val = float(equity)
            if eq_val > 0:
                risk_capital = eq_val
                risk_capital_source = "equity"
            elif eq_val < 0:
                rejection_reason = f"Account equity is negative ({eq_val:,.2f})"
            else:  # eq_val == 0
                is_init = getattr(state.account, "is_initialized", True)
                open_positions = len(state.portfolio) if state.portfolio is not None else 0
                if (not is_init) and (open_positions == 0):
                    if is_valid_finite_number(cash) and float(cash) > 0:
                        risk_capital = float(cash)
                        risk_capital_source = "cash_bootstrap"
                    else:
                        rejection_reason = "Account is uninitialized but has no valid positive cash base"
                else:
                    rejection_reason = "Account equity is zero with active account or open positions (data inconsistency)"
        else:
            # Equity is unavailable (None, NaN) or invalid (inf / non-numeric)
            if equity is not None and isinstance(equity, (int, float)) and math.isinf(equity):
                rejection_reason = f"Account equity is non-finite/invalid ({equity})"
            elif is_valid_finite_number(cash) and float(cash) > 0:
                risk_capital = float(cash)
                risk_capital_source = "cash_bootstrap"
            else:
                rejection_reason = "Account equity is unavailable and no valid positive cash base exists"

        if rejection_reason is not None:
            state.risk_capital_base = 0.0
            state.risk_capital_source = risk_capital_source
            state.base_risk_budget = 0.0
            state.requested_risk_budget = 0.0
            state.governed_risk_budget = 0.0
            state.permitted_risk_budget = 0.0
            state.add_rejection(rejection_reason)
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason=rejection_reason,
            )
            return state

        # Successful resolution of risk capital
        state.risk_capital_base = float(risk_capital)
        state.risk_capital_source = risk_capital_source
        if state.risk_equity_snapshot <= 0:
            state.risk_equity_snapshot = float(risk_capital)

        r0 = state.risk_capital_base * base_risk_pct
        state.base_risk_budget = r0
        state.requested_risk_budget = r0
        state.governed_risk_budget = r0
        state.permitted_risk_budget = r0

        msg = (
            f"Risk Capital Base = ${state.risk_capital_base:,.2f} (Source: {risk_capital_source}), "
            f"Base Risk % = {base_risk_pct:.4f} -> Base Risk Budget R0 = ${r0:,.2f}"
        )
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Calculated base risk budget R0 = ${r0:,.2f} from {risk_capital_source}",
        )
        return state


# Backward-compatibility alias
BaseRiskModule = BaseRiskBudgetModule

