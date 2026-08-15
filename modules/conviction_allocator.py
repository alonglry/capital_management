"""
Module 2 — Dynamic Conviction Risk Allocator.
"""

import math
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import RiskTransformer
from capital_management.modules.conviction_mapping import (
    ConvictionMapping,
    LinearConvictionMapping,
    PowerConvictionMapping,
)


class ConvictionRiskAllocatorModule(RiskTransformer):
    """
    Module 2: Converts strategy conviction into a requested monetary risk budget.

    Calculates long & short conviction independently, net conviction, directional strength,
    and signal conflict penalty, then maps directional strength to requested risk.
    """

    def __init__(self, mapping: Optional[ConvictionMapping] = None):
        self._custom_mapping = mapping

    @property
    def name(self) -> str:
        return "conviction_allocator"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "base_risk_budget": state.base_risk_budget,
            "slope_long": getattr(state.trade, "slope_long", None),
            "threshold_long": getattr(state.trade, "threshold_long", None),
            "slope_short": getattr(state.trade, "slope_short", None),
            "threshold_short": getattr(state.trade, "threshold_short", None),
            "config": state.config.conviction_risk,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "long_conviction": state.long_conviction,
            "short_conviction": state.short_conviction,
            "net_conviction": state.net_conviction,
            "directional_strength": state.directional_strength,
            "signal_conflict": state.signal_conflict,
            "conviction_multiplier": state.conviction_multiplier,
            "conflict_multiplier": state.conflict_multiplier,
            "requested_risk_budget": state.requested_risk_budget,
            "requested_risk_pct": state.requested_risk_pct,
        }

    def _resolve_mapping(self, state: CapitalManagementState) -> ConvictionMapping:
        if self._custom_mapping is not None:
            return self._custom_mapping

        config = state.config.conviction_risk
        if config.mapping_type.lower() == "power":
            return PowerConvictionMapping(gamma=config.power_gamma)
        return LinearConvictionMapping()

    def _calc_side_conviction(
        self, slope: Union[float, pd.Series], threshold: Union[float, pd.Series], mult: float
    ) -> Union[float, pd.Series]:
        is_vector = isinstance(slope, pd.Series) or isinstance(threshold, pd.Series)

        if is_vector:
            s = pd.Series(slope) if not isinstance(slope, pd.Series) else slope
            t = pd.Series(threshold) if not isinstance(threshold, pd.Series) else threshold
            # Guard against invalid negative or NaN thresholds
            t = t.apply(lambda v: v if pd.notna(v) and float(v) > 0 else np.nan)
            s = s.apply(lambda v: v if pd.notna(v) and not math.isinf(float(v)) else 0.0)

            max_c = t * mult
            denom = max_c - t
            denom = denom.replace(0, np.nan)
            raw = (s - t) / denom
            return raw.fillna(0.0).clip(lower=0.0, upper=1.0)
        else:
            s_val = float(slope) if slope is not None and pd.notna(slope) and not math.isinf(float(slope)) else 0.0
            t_val = float(threshold) if threshold is not None and pd.notna(threshold) and not math.isinf(float(threshold)) else 0.0

            if t_val <= 0:
                return 0.0

            max_c = t_val * mult
            denom = max_c - t_val
            if abs(denom) < 1e-12:
                raw = 0.0
            else:
                raw = (s_val - t_val) / denom
            return max(0.0, min(1.0, raw))

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        risk_capital = state.risk_capital_base
        if (
            risk_capital is None
            or not isinstance(risk_capital, (int, float))
            or isinstance(risk_capital, bool)
            or not math.isfinite(risk_capital)
            or risk_capital <= 0
        ):
            state.add_rejection("Risk capital base is unavailable or non-positive.")
            state.requested_risk_budget = 0.0
            state.requested_risk_pct = 0.0
            state.governed_risk_budget = 0.0
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Risk capital base is unavailable or non-positive.",
            )
            return state

        base_budget = state.base_risk_budget
        cfg = state.config.conviction_risk

        slope_l = getattr(state.trade, "slope_long", None)
        if slope_l is None:
            slope_l = 0.0

        thresh_l = getattr(state.trade, "threshold_long", None)
        if thresh_l is None:
            thresh_l = 0.0

        slope_s = getattr(state.trade, "slope_short", None)
        if slope_s is None:
            slope_s = 0.0

        thresh_s = getattr(state.trade, "threshold_short", None)
        if thresh_s is None:
            thresh_s = 0.0

        is_vector = any(
            isinstance(x, pd.Series) for x in [slope_l, thresh_l, slope_s, thresh_s]
        )

        mult = cfg.conviction_threshold_multiplier
        c_long = self._calc_side_conviction(slope_l, thresh_l, mult)
        c_short = self._calc_side_conviction(slope_s, thresh_s, mult)

        if is_vector:
            c_long = pd.Series(c_long)
            c_short = pd.Series(c_short)
            net_c = c_long - c_short
            dir_str = net_c.abs()
            sig_conflict = np.minimum(c_long, c_short)

            conflict_mult = 1.0 - (cfg.conflict_penalty * sig_conflict)
            mapping_fn = self._resolve_mapping(state)
            mapped_str = mapping_fn(dir_str)
            conv_mult = cfg.min_multiplier + (cfg.max_multiplier - cfg.min_multiplier) * mapped_str

            requested_budget = base_budget * conv_mult * conflict_mult
            requested_pct = requested_budget / risk_capital
        else:
            c_long_val = float(c_long)
            c_short_val = float(c_short)
            net_c_val = c_long_val - c_short_val
            dir_str_val = abs(net_c_val)
            sig_conflict_val = min(c_long_val, c_short_val)

            conflict_mult_val = 1.0 - (cfg.conflict_penalty * sig_conflict_val)
            mapping_fn = self._resolve_mapping(state)
            mapped_str_val = float(mapping_fn(dir_str_val))
            conv_mult_val = cfg.min_multiplier + (cfg.max_multiplier - cfg.min_multiplier) * mapped_str_val

            requested_budget_val = base_budget * conv_mult_val * conflict_mult_val
            requested_pct_val = requested_budget_val / risk_capital

            c_long = c_long_val
            c_short = c_short_val
            net_c = net_c_val
            dir_str = dir_str_val
            sig_conflict = sig_conflict_val
            conflict_mult = conflict_mult_val
            conv_mult = conv_mult_val
            requested_budget = requested_budget_val
            requested_pct = requested_pct_val

        # Update state metrics
        state.long_conviction = c_long
        state.short_conviction = c_short
        state.net_conviction = net_c
        state.directional_strength = dir_str
        state.signal_conflict = sig_conflict
        state.conviction_multiplier = conv_mult
        state.conflict_multiplier = conflict_mult
        state.requested_risk_budget = requested_budget
        state.requested_risk_pct = requested_pct
        state.governed_risk_budget = requested_budget

        status = "PASS"
        if is_vector:
            reason = f"Calculated vectorized conviction requested risk budget (Series length={len(requested_budget)})"
            msg = "Vectorized conviction completed"
        else:
            reason = f"Calculated conviction requested risk budget = ${requested_budget:,.2f} ({requested_pct:.2%})"
            msg = f"Long = {c_long:.2f}, Short = {c_short:.2f}, Net = {net_c:.2f}, Str = {dir_str:.2f}, Conflict = {sig_conflict:.2f} -> Requested Risk = ${requested_budget:,.2f}"

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
