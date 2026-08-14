"""
Module 3 — Volatility Governor.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class VolatilityGovernorModule(BaseRiskModule):
    """
    Module 3: Adjusts risk budget based on ATR Ratio (Current ATR / Reference ATR).

    Formula:
        ATR Ratio = Current ATR / Reference ATR
        R2 = R_prev * Volatility Multiplier
    """

    @property
    def name(self) -> str:
        return "volatility_governor"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        atr_ratio = self._resolve_atr_ratio(state)
        return {
            "symbol": state.trade.symbol,
            "atr_ratio": atr_ratio,
            "prev_budget": state.adjusted_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "volatility_multiplier": state.volatility_multiplier,
            "adjusted_risk_budget": state.adjusted_risk_budget,
        }

    def _resolve_atr_ratio(self, state: CapitalManagementState) -> float:
        """
        Resolves ATR ratio from TradeCandidate or MarketData container.
        """
        # 1. Directly specified in TradeCandidate
        if state.trade.atr_ratio is not None and state.trade.atr_ratio > 0:
            return state.trade.atr_ratio

        symbol = state.trade.symbol

        # 2. Derived from TradeCandidate ATR or MarketData ATR and reference ATR
        curr_atr = state.trade.atr
        if curr_atr is None and isinstance(state.market_data.atr, dict):
            curr_atr = state.market_data.atr.get(symbol)

        ref_atr = None
        if isinstance(state.market_data.reference_atr, dict):
            ref_atr = state.market_data.reference_atr.get(symbol)

        if curr_atr is not None and ref_atr is not None and isinstance(ref_atr, (int, float)) and ref_atr > 0:
            return float(curr_atr / ref_atr)

        # Fallback if no ATR metrics available
        return 1.0

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        atr_ratio = self._resolve_atr_ratio(state)

        # Look up multiplier tier
        multiplier = 1.00
        for rule in state.config.volatility_rules:
            if rule.min_ratio <= atr_ratio < rule.max_ratio:
                multiplier = rule.multiplier
                break

        prev_budget = state.adjusted_risk_budget
        r2 = prev_budget * multiplier

        state.volatility_multiplier = multiplier
        state.adjusted_risk_budget = r2

        msg = f"Symbol = {state.trade.symbol}, ATR Ratio = {atr_ratio:.2f}, Multiplier = {multiplier:.2f}, Budget: ${prev_budget:,.2f} -> ${r2:,.2f}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Applied volatility multiplier {multiplier:.2f} (ATR ratio={atr_ratio:.2f}), adjusted budget = ${r2:,.2f}",
        )
        return state
