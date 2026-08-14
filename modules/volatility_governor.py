"""
Module 4 — Volatility Governor.
"""

from typing import Any, Dict, Optional

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskTransformer


class VolatilityGovernorModule(RiskTransformer):
    """
    Module 4: Adjusts governed risk budget based on ATR Ratio (Current ATR / Reference ATR).

    Formula:
        ATR Ratio = Current ATR / Reference ATR
        governed_risk_budget = governed_risk_budget * Volatility Multiplier
    """

    @property
    def name(self) -> str:
        return "volatility_governor"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        atr_ratio = self._resolve_atr_ratio(state)
        return {
            "symbol": state.trade.symbol,
            "atr_ratio": atr_ratio,
            "missing_volatility_policy": state.config.missing_volatility_policy,
            "prev_governed_budget": state.governed_risk_budget,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "volatility_multiplier": state.volatility_multiplier,
            "governed_risk_budget": state.governed_risk_budget,
        }

    def _resolve_atr_ratio(self, state: CapitalManagementState) -> Optional[float]:
        if state.trade.atr_ratio is not None and state.trade.atr_ratio > 0:
            return float(state.trade.atr_ratio)

        symbol = state.trade.symbol
        curr_atr = state.trade.atr
        if curr_atr is None and isinstance(state.market_data.atr, dict):
            curr_atr = state.market_data.atr.get(symbol)

        ref_atr = None
        if isinstance(state.market_data.reference_atr, dict):
            ref_atr = state.market_data.reference_atr.get(symbol)

        if curr_atr is not None and ref_atr is not None and isinstance(ref_atr, (int, float)) and ref_atr > 0:
            return float(curr_atr / ref_atr)

        return None

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        atr_ratio = self._resolve_atr_ratio(state)
        policy = state.config.missing_volatility_policy.lower()

        if atr_ratio is None:
            if policy == "reject":
                state.add_rejection(f"Missing volatility / ATR metrics for symbol '{state.trade.symbol}' (policy = reject)")
                state.volatility_multiplier = 0.0
                state.governed_risk_budget = 0.0
                state.module_results[self.name] = ModuleResult(
                    module_name=self.name,
                    enabled=True,
                    input_summary=self._get_input_summary(state),
                    output_summary=self._get_output_summary(state),
                    status="REJECT",
                    reason=f"Missing volatility metrics for '{state.trade.symbol}' (policy = reject)",
                )
                return state
            elif policy == "conservative":
                multiplier = 0.50
                state.add_warning(f"Missing volatility metrics for '{state.trade.symbol}'; applying conservative multiplier {multiplier:.2f}")
                atr_ratio = 2.0
            else:  # 'neutral'
                multiplier = 1.00
                state.add_warning(f"Missing volatility metrics for '{state.trade.symbol}'; applying neutral multiplier {multiplier:.2f}")
                atr_ratio = 1.00
        else:
            multiplier = 1.00
            for rule in state.config.volatility_rules:
                if rule.min_ratio <= atr_ratio < rule.max_ratio:
                    multiplier = rule.multiplier
                    break

        prev_budget = state.governed_risk_budget
        r2 = prev_budget * multiplier

        state.volatility_multiplier = multiplier
        state.governed_risk_budget = r2

        msg = f"Symbol = {state.trade.symbol}, ATR Ratio = {atr_ratio:.2f}, Multiplier = {multiplier:.2f}, Governed Budget: ${prev_budget:,.2f} -> ${r2:,.2f}"
        state.add_trace(self.name, msg)

        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary=self._get_input_summary(state),
            output_summary=self._get_output_summary(state),
            status="PASS",
            reason=f"Applied volatility multiplier {multiplier:.2f} (ATR ratio={atr_ratio:.2f}), governed budget = ${r2:,.2f}",
        )
        return state
