"""
Module 6 — Correlation-Adjusted Portfolio Risk.
"""

import math
from typing import Any, Dict, List, Tuple

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class CorrelationRiskModule(BaseRiskModule):
    """
    Module 6: Calculates correlation-adjusted portfolio risk using matrix math.

    Formula:
        r = vector of percentage-of-equity risks [r1, r2, ..., r_candidate]
        Sigma = correlation matrix
        R_portfolio = sqrt(r^T * Sigma * r)
    """

    @property
    def name(self) -> str:
        return "correlation_check"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        symbols = [p.symbol for p in state.portfolio] + [state.trade.symbol]
        return {
            "symbols": symbols,
            "max_correlation_adjusted_risk_pct": state.config.max_correlation_adjusted_risk_pct,
            "fallback_policy": state.config.correlation_fallback_policy,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "correlation_adjusted_risk": state.correlation_adjusted_risk,
            "projected_correlation_adjusted_risk": state.projected_correlation_adjusted_risk,
            "correlation_risk_capacity": state.correlation_risk_capacity,
        }

    def _build_correlation_matrix(
        self, symbols: List[str], state: CapitalManagementState
    ) -> Tuple[List[List[float]], bool]:
        """
        Constructs correlation matrix for symbols or applies configured fallback policy.

        Returns:
            (matrix, is_fallback_used)
        """
        raw_matrix = state.market_data.correlation_matrix
        n = len(symbols)

        if not raw_matrix:
            return self._apply_matrix_fallback(n, state)

        # Check if all pairs are present
        matrix = [[0.0] * n for _ in range(n)]
        missing = False

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    sym_i = symbols[i]
                    sym_j = symbols[j]
                    val = raw_matrix.get(sym_i, {}).get(sym_j)
                    if val is None:
                        val = raw_matrix.get(sym_j, {}).get(sym_i)
                    if val is None:
                        missing = True
                        break
                    matrix[i][j] = float(val)
            if missing:
                break

        if missing:
            return self._apply_matrix_fallback(n, state)

        return matrix, False

    def _apply_matrix_fallback(
        self, n: int, state: CapitalManagementState
    ) -> Tuple[List[List[float]], bool]:
        policy = state.config.correlation_fallback_policy

        if policy == "assume_max_correlation":
            state.add_warning("Correlation matrix unavailable; using assume_max_correlation (all corr = 1.0).")
            return [[1.0] * n for _ in range(n)], True
        elif policy == "assume_zero_correlation":
            state.add_warning("Correlation matrix unavailable; using assume_zero_correlation (identity matrix).")
            matrix = [[0.0] * n for _ in range(n)]
            for i in range(n):
                matrix[i][i] = 1.0
            return matrix, True
        else:
            # For 'ignore_module' or 'reject', handle at caller level
            matrix = [[0.0] * n for _ in range(n)]
            for i in range(n):
                matrix[i][i] = 1.0
            return matrix, True

    def _calc_portfolio_risk(self, r: List[float], Sigma: List[List[float]]) -> float:
        """
        Computes sqrt(r^T * Sigma * r).
        """
        n = len(r)
        variance = 0.0
        for i in range(n):
            for j in range(n):
                variance += r[i] * Sigma[i][j] * r[j]
        return math.sqrt(max(0.0, variance))

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        if equity <= 0:
            return state

        policy = state.config.correlation_fallback_policy
        raw_matrix = state.market_data.correlation_matrix

        if not raw_matrix and policy == "reject":
            state.add_rejection("Correlation matrix is missing and fallback policy is set to 'reject'.")
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Correlation data unavailable (fallback policy = reject).",
            )
            return state

        if not raw_matrix and policy == "ignore_module":
            state.add_warning("Correlation data unavailable; skipping correlation module check.")
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="SKIPPED",
                reason="Correlation data unavailable (fallback policy = ignore_module).",
            )
            return state

        symbols = [p.symbol for p in state.portfolio] + [state.trade.symbol]
        Sigma, is_fallback = self._build_correlation_matrix(symbols, state)

        # Risk vectors as % of equity
        r_curr = [p.monetary_risk_at_stop / equity for p in state.portfolio]
        r_cand = state.adjusted_risk_budget / equity
        r_proj = r_curr + [r_cand]

        n_curr = len(r_curr)
        Sigma_curr = [[Sigma[i][j] for j in range(n_curr)] for i in range(n_curr)] if n_curr > 0 else []

        curr_corr_risk_pct = self._calc_portfolio_risk(r_curr, Sigma_curr) if n_curr > 0 else 0.0
        proj_corr_risk_pct = self._calc_portfolio_risk(r_proj, Sigma)

        limit_pct = state.config.max_correlation_adjusted_risk_pct
        capacity_pct = max(0.0, limit_pct - curr_corr_risk_pct)

        state.correlation_adjusted_risk = curr_corr_risk_pct
        state.projected_correlation_adjusted_risk = proj_corr_risk_pct
        state.correlation_risk_capacity = capacity_pct * equity

        status = "PASS"
        reason = f"Projected correlation-adjusted risk {proj_corr_risk_pct:.2%} <= limit {limit_pct:.2%}"

        if proj_corr_risk_pct > limit_pct:
            status = "REJECT"
            reason = f"Projected correlation-adjusted risk {proj_corr_risk_pct:.2%} exceeds limit {limit_pct:.2%}"
            state.add_rejection(reason)

        msg = f"Curr Corr Risk = {curr_corr_risk_pct:.2%}, Proj Corr Risk = {proj_corr_risk_pct:.2%}, Limit = {limit_pct:.2%}, Status = {status}"
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
