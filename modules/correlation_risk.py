"""
Module 7 — Correlation Risk.
"""

import math
from typing import Any, Dict, List, Tuple

import numpy as np

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskConstraint


class CorrelationRiskModule(RiskConstraint):
    """
    Module 7: Hard risk constraint computing maximum correlation-adjusted risk capacity via quadratic variance solver.

    Projected Portfolio Variance:
        V(x) = r' * Sigma * r + 2 * x * (c' * r) + x^2
    Solves x^2 + 2(c'r)x + (r'Sigma r - max_risk^2) <= 0 for positive root x*.
    """

    @property
    def name(self) -> str:
        return "correlation_check"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        symbols = [p.symbol for p in state.portfolio] + [state.trade.symbol]
        return {
            "symbols": symbols,
            "max_correlation_adjusted_risk_pct": state.config.max_correlation_adjusted_risk_pct,
            "invalid_correlation_policy": state.config.invalid_correlation_policy,
            "missing_correlation_policy": state.config.missing_correlation_policy,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "correlation_risk_capacity": state.correlation_risk_capacity,
            "permitted_risk_budget": state.permitted_risk_budget,
            "correlation_adjusted_risk": state.correlation_adjusted_risk,
            "projected_correlation_adjusted_risk": state.projected_correlation_adjusted_risk,
        }

    def _validate_and_repair_matrix(
        self, matrix: np.ndarray, state: CapitalManagementState
    ) -> Tuple[np.ndarray, bool, str]:
        """
        Validates correlation matrix properties:
        1. Square, 2. Symmetric, 3. Diagonal == 1, 4. Elements in [-1, 1], 5. Positive Semidefinite.
        """
        n, m = matrix.shape
        if n != m:
            return matrix, False, f"Matrix is not square ({n}x{m})"

        if not np.allclose(matrix, matrix.T, atol=1e-4):
            return matrix, False, "Matrix is not symmetric"

        if not np.allclose(np.diag(matrix), 1.0, atol=1e-3):
            return matrix, False, "Matrix diagonal elements do not equal 1.0"

        if np.any(matrix < -1.0 - 1e-4) or np.any(matrix > 1.0 + 1e-4):
            return matrix, False, "Matrix elements fall outside [-1.0, 1.0]"

        eigvals = np.linalg.eigvalsh(matrix)
        if np.min(eigvals) < -1e-4:
            policy = state.config.invalid_correlation_policy.lower()
            if policy == "repair":
                # Nearest PSD projection
                vals, vecs = np.linalg.eigh(matrix)
                vals = np.maximum(vals, 1e-6)
                repaired = vecs @ np.diag(vals) @ vecs.T
                # Rescale diagonal to 1.0
                d = np.sqrt(np.diag(repaired))
                repaired = repaired / np.outer(d, d)
                state.add_warning("Correlation matrix was non-PSD; repaired using nearest PSD projection.")
                return repaired, True, "Repaired non-PSD matrix"
            else:
                return matrix, False, f"Matrix is not positive semidefinite (min eigenvalue = {np.min(eigvals):.6f})"

        return matrix, True, "Valid"

    def _extract_correlation_matrix(
        self, symbols: List[str], state: CapitalManagementState
    ) -> Tuple[np.ndarray, bool, str]:
        raw_matrix = state.market_data.correlation_matrix
        policy = state.config.missing_correlation_policy.lower()
        if policy not in ("assume_zero", "repair") and state.config.correlation_fallback_policy.lower() == "assume_zero_correlation":
            policy = "assume_zero"
        n = len(symbols)
        if n == 1:
            return np.array([[1.0]], dtype=np.float64), True, "Single trade (self correlation 1.0)"

        if not raw_matrix:
            if policy == "assume_zero":
                state.add_warning("Missing correlation matrix; using assume_zero fallback (identity matrix).")
                return np.eye(n), True, "Assume zero correlation"
            return np.eye(n), False, "Missing correlation matrix data"

        matrix = np.zeros((n, n), dtype=np.float64)
        missing = False

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i, j] = 1.0
                else:
                    sym_i = symbols[i]
                    sym_j = symbols[j]
                    val = raw_matrix.get(sym_i, {}).get(sym_j)
                    if val is None:
                        val = raw_matrix.get(sym_j, {}).get(sym_i)
                    if val is None:
                        missing = True
                        break
                    matrix[i, j] = float(val)
            if missing:
                break

        if missing:
            if policy == "assume_zero":
                state.add_warning("Incomplete correlation matrix; using assume_zero fallback.")
                return np.eye(n), True, "Incomplete matrix (assume zero)"
            return np.eye(n), False, "Incomplete correlation matrix for required symbols"

        return self._validate_and_repair_matrix(matrix, state)

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        if equity <= 0:
            state.add_rejection("Account equity is non-positive for correlation risk calculation.")
            state.correlation_risk_capacity = 0.0
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

        existing_positions = state.portfolio
        symbols = [p.symbol for p in existing_positions] + [state.trade.symbol]
        n_existing = len(existing_positions)

        Sigma, is_valid, msg_matrix = self._extract_correlation_matrix(symbols, state)

        if not is_valid:
            state.add_rejection(f"Invalid or missing correlation matrix: {msg_matrix}")
            state.correlation_risk_capacity = 0.0
            state.permitted_risk_budget = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason=f"Correlation matrix error: {msg_matrix}",
            )
            return state

        # Normalized risk vectors r (% of equity)
        r_existing = np.array([p.monetary_risk_at_stop / equity for p in existing_positions], dtype=np.float64) if n_existing > 0 else np.array([], dtype=np.float64)
        max_risk_pct = state.config.max_correlation_adjusted_risk_pct

        if n_existing == 0:
            # Single trade case: capacity = max_risk_pct * equity
            corr_capacity = max_risk_pct * equity
            curr_corr_risk_pct = 0.0
        else:
            Sigma_curr = Sigma[:n_existing, :n_existing]
            c_vector = Sigma[:n_existing, n_existing]  # candidate correlation vector with existing

            var_curr = float(r_existing.T @ Sigma_curr @ r_existing)
            curr_corr_risk_pct = math.sqrt(max(0.0, var_curr))

            c_dot_r = float(c_vector @ r_existing)
            c_term = c_dot_r
            const_term = var_curr - (max_risk_pct ** 2)

            discriminant = (c_term ** 2) - const_term

            if discriminant < 0:
                # Portfolio already exceeds max correlation risk
                x_star = 0.0
            else:
                x_star = -c_term + math.sqrt(discriminant)

            corr_capacity = max(0.0, float(x_star * equity))

        state.correlation_risk_capacity = corr_capacity
        state.correlation_adjusted_risk = curr_corr_risk_pct

        prev_permitted = state.permitted_risk_budget
        new_permitted = min(prev_permitted, corr_capacity)
        state.permitted_risk_budget = new_permitted

        # Calculate projected correlation risk after candidate addition
        x_cand_pct = new_permitted / equity
        if n_existing > 0:
            r_proj = np.append(r_existing, x_cand_pct)
            proj_var = float(r_proj.T @ Sigma @ r_proj)
            proj_corr_risk_pct = math.sqrt(max(0.0, proj_var))
        else:
            proj_corr_risk_pct = x_cand_pct

        state.projected_correlation_adjusted_risk = proj_corr_risk_pct

        if corr_capacity <= 0:
            status = "REJECT"
            reason = f"Existing portfolio correlation risk ({curr_corr_risk_pct:.2%}) meets or exceeds maximum limit ({max_risk_pct:.2%})"
            state.add_rejection(reason)
        elif new_permitted < prev_permitted:
            status = "PASS"
            reason = f"Correlation capacity (${corr_capacity:,.2f}) constrained permitted risk from ${prev_permitted:,.2f} to ${new_permitted:,.2f}"
            state.add_warning(reason)
        else:
            status = "PASS"
            reason = f"Correlation risk capacity (${corr_capacity:,.2f}) satisfies requested permitted risk (${new_permitted:,.2f})"

        msg = f"Curr Corr Risk = {curr_corr_risk_pct:.2%}, Proj Corr Risk = {proj_corr_risk_pct:.2%}, Capacity = ${corr_capacity:,.2f}, Permitted Risk: ${prev_permitted:,.2f} -> ${new_permitted:,.2f}, Status = {status}"
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
