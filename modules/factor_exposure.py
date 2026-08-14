"""
Module 7 — Factor Exposure.
"""

from typing import Any, Dict, List

from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_module import BaseRiskModule


class FactorExposureModule(BaseRiskModule):
    """
    Module 7: Evaluates portfolio factor exposures for Forex currencies and Equity factors.

    Recognizes multi-pair net currency factor positioning (e.g. EURUSD Long + GBPUSD Long -> USD = -2.0)
    as well as equity sector weight, beta, and country limits.
    """

    @property
    def name(self) -> str:
        return "factor_check"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "symbol": state.trade.symbol,
            "asset_class": state.trade.asset_class,
            "factor_limits": state.config.factor_limits,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "current_factor_exposure": state.current_factor_exposure,
            "projected_factor_exposure": state.projected_factor_exposure,
            "factor_limit_utilization": state.factor_limit_utilization,
            "factor_constraint_status": state.factor_constraint_status,
        }

    def _extract_factors(self, item: Position | TradeCandidate, equity: float) -> Dict[str, float]:
        """
        Extracts factor exposures for a position or trade candidate.
        """
        factors: Dict[str, float] = {}

        # 1. Currency exposure dict (if explicitly provided)
        if item.currency_exposure:
            scale = item.quantity if isinstance(item, Position) else 1.0
            for ccy, weight in item.currency_exposure.items():
                factors[ccy] = factors.get(ccy, 0.0) + (weight * scale)
        elif item.asset_class.lower() == "forex" and len(item.symbol) == 6:
            # Automatic standard 6-character FX symbol decomposition (e.g. EURUSD)
            base_ccy = item.symbol[:3].upper()
            quote_ccy = item.symbol[3:].upper()
            direction = 1.0 if item.side.lower() == "long" else -1.0
            scale = item.quantity if isinstance(item, Position) else 1.0
            factors[base_ccy] = factors.get(base_ccy, 0.0) + (direction * scale)
            factors[quote_ccy] = factors.get(quote_ccy, 0.0) - (direction * scale)
        else:
            # Equity position weight estimation
            if isinstance(item, Position):
                pos_val = item.quantity * item.current_price
            else:
                # TradeCandidate weight estimation
                stop_dist = abs(item.entry_price - item.proposed_stop_price)
                est_shares = (equity * 0.005) / stop_dist if stop_dist > 0 else 0.0
                pos_val = est_shares * item.entry_price

            weight = pos_val / equity if equity > 0 else 0.0

            if item.sector:
                factors[item.sector] = factors.get(item.sector, 0.0) + weight
            if item.country:
                factors[item.country] = factors.get(item.country, 0.0) + weight
            if item.beta is not None:
                direction = 1.0 if item.side.lower() == "long" else -1.0
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

        if exceeded:
            state.factor_constraint_status = "REJECT"
            status = "REJECT"
            reason = "; ".join(exceeded)
            for err in exceeded:
                state.add_rejection(err)
        else:
            state.factor_constraint_status = "PASS"
            status = "PASS"
            reason = "All factor exposures are within configured limits"

        state.factor_exposure = projected_exposures

        msg = f"Projected Factors = {projected_exposures}, Status = {status}"
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
