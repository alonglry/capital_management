from __future__ import annotations

"""
Module 8 — Factor Risk.
"""

from typing import Any, Dict, List

from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_module import RiskConstraint


class FactorExposureModule(RiskConstraint):
    """
    Module 8: Hard risk constraint computing factor-risk capacity for currency factors and equity factors.
    Preserves sign for long (+1.0) and short (-1.0) positions across base/quote currencies and equity factors.
    """

    @property
    def name(self) -> str:
        return "factor_check"

    @property
    def module_type(self) -> str:
        return "constraint"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "symbol": state.trade.symbol,
            "asset_class": state.trade.asset_class,
            "factor_limits": state.config.factor_limits,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "factor_risk_capacity": state.factor_risk_capacity,
            "permitted_risk_budget": state.permitted_risk_budget,
            "current_factor_exposure": state.current_factor_exposure,
            "projected_factor_exposure": state.projected_factor_exposure,
            "factor_limit_utilization": state.factor_limit_utilization,
            "factor_constraint_status": state.factor_constraint_status,
        }

    def _extract_factors(self, item: Position | TradeCandidate, equity: float) -> Dict[str, float]:
        factors: Dict[str, float] = {}

        if item.currency_exposure:
            scale = item.quantity if isinstance(item, Position) else 1.0
            direction = 1.0 if item.side.lower() == "long" else -1.0
            for ccy, weight in item.currency_exposure.items():
                factors[ccy] = factors.get(ccy, 0.0) + (weight * scale * direction)
        elif item.asset_class.upper() == "FOREX" and len(item.symbol) >= 6:
            base_ccy = item.symbol[:3].upper()
            quote_ccy = item.symbol[3:6].upper()
            direction = 1.0 if item.side.lower() == "long" else -1.0
            scale = item.quantity if isinstance(item, Position) else 1.0
            factors[base_ccy] = factors.get(base_ccy, 0.0) + (direction * scale)
            factors[quote_ccy] = factors.get(quote_ccy, 0.0) - (direction * scale)
        else:
            if isinstance(item, Position):
                pos_val = item.quantity * item.current_price
            else:
                stop_dist = abs(item.entry_price - item.proposed_stop_price)
                est_shares = (equity * 0.005) / stop_dist if stop_dist > 0 else 0.0
                pos_val = est_shares * item.entry_price

            weight = pos_val / equity if equity > 0 else 0.0
            direction = 1.0 if item.side.lower() == "long" else -1.0

            if item.sector:
                factors[item.sector] = factors.get(item.sector, 0.0) + (weight * direction)
            if item.country:
                factors[item.country] = factors.get(item.country, 0.0) + (weight * direction)
            if item.beta is not None:
                factors["market_beta"] = factors.get("market_beta", 0.0) + (item.beta * direction * weight)

        return factors

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        equity = state.account.equity
        current_exposures: Dict[str, float] = {}

        for pos in state.portfolio:
            pos_factors = self._extract_factors(pos, equity)
            for f, val in pos_factors.items():
                current_exposures[f] = current_exposures.get(f, 0.0) + val

        cand_factors = self._extract_factors(state.trade, equity)
        projected_exposures = dict(current_exposures)
        for f, val in cand_factors.items():
            projected_exposures[f] = projected_exposures.get(f, 0.0) + val

        state.current_factor_exposure = current_exposures
        state.projected_factor_exposure = projected_exposures

        limits = state.config.factor_limits
        utilization: Dict[str, float] = {}
        exceeded: List[str] = []

        for factor, proj_val in projected_exposures.items():
            if factor in limits and limits[factor] > 0:
                limit_val = limits[factor]
                util_pct = abs(proj_val) / limit_val
                utilization[factor] = util_pct

                if abs(proj_val) > limit_val:
                    exceeded.append(f"{factor} factor exposure ({proj_val:+.2f}) exceeds limit ({limit_val:.2f})")

        state.factor_limit_utilization = utilization

        # Compute factor capacity
        factor_capacity = float("inf")
        for factor, val_cand in cand_factors.items():
            if factor in limits and limits[factor] > 0:
                limit_val = limits[factor]
                curr_val = current_exposures.get(factor, 0.0)
                rem_capacity_units = max(0.0, limit_val - abs(curr_val))
                if abs(val_cand) > 0:
                    scale_factor = rem_capacity_units / abs(val_cand)
                    factor_capacity = min(factor_capacity, state.permitted_risk_budget * scale_factor)

        if factor_capacity == float("inf"):
            factor_capacity = state.permitted_risk_budget

        state.factor_risk_capacity = factor_capacity
        prev_permitted = state.permitted_risk_budget
        new_permitted = min(prev_permitted, factor_capacity)
        state.permitted_risk_budget = new_permitted

        if exceeded:
            state.factor_constraint_status = "REJECT"
            status = "REJECT"
            reason = "; ".join(exceeded)
            for err in exceeded:
                state.add_rejection(err)
        else:
            state.factor_constraint_status = "PASS"
            status = "PASS"
            reason = f"All factor exposures within limits (factor capacity = ${factor_capacity:,.2f})"

        state.factor_exposure = projected_exposures

        msg = f"Factor Capacity = ${factor_capacity:,.2f}, Permitted Risk: ${prev_permitted:,.2f} -> ${new_permitted:,.2f}, Status = {status}"
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
