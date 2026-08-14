"""
Module 9 — Position Sizing.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class PositionSizingModule(BaseRiskModule):
    """
    Module 9: Converts monetary risk budget into position size (shares/contracts for Equities, lots/units for Forex).

    Formulas:
        Equities: raw_quantity = risk_budget / stop_distance
        Forex: raw_lots = risk_budget / (pips * pip_value_per_lot)
    """

    @property
    def name(self) -> str:
        return "position_sizing"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "symbol": state.trade.symbol,
            "asset_class": state.trade.asset_class,
            "adjusted_risk_budget": state.adjusted_risk_budget,
            "stop_distance": state.stop_distance,
            "pip_value_per_lot": state.trade.pip_value_per_lot,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "raw_position_size": state.raw_position_size,
            "rounded_position_size": state.rounded_position_size,
        }

    def _apply_rounding(self, raw_size: float, asset_class: str, state: CapitalManagementState) -> float:
        rules = state.config.rounding_rules
        rule = rules.get(asset_class.lower(), rules.get("default", "round_2dp"))

        if rule == "floor_int":
            return float(math.floor(raw_size))
        elif rule == "round_int":
            return float(round(raw_size))
        elif rule == "round_2dp":
            return round(raw_size, 2)
        elif rule == "round_4dp":
            return round(raw_size, 4)
        else:
            return raw_size

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        budget = state.adjusted_risk_budget
        stop_dist = state.stop_distance
        asset_class = state.trade.asset_class.lower()

        if budget <= 0 or stop_dist <= 0:
            state.raw_position_size = 0.0
            state.rounded_position_size = 0.0
            state.final_position_size = 0.0
            status = "REJECT"
            reason = f"Cannot calculate position size with risk_budget={budget:,.2f} or stop_distance={stop_dist}"
            state.add_rejection(reason)
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status=status,
                reason=reason,
            )
            return state

        if asset_class == "forex":
            # Forex calculation
            pip_val = state.trade.pip_value_per_lot
            symbol = state.trade.symbol.upper()
            pip_size = 0.01 if "JPY" in symbol else 0.0001

            if pip_val is not None and pip_val > 0:
                pips = stop_dist / pip_size
                raw_size = budget / (pips * pip_val)
            else:
                # Default units / direct price distance
                point_val = state.trade.point_value or 1.0
                raw_size = budget / (stop_dist * point_val)
        else:
            # Equities / default shares
            point_val = state.trade.point_value or 1.0
            raw_size = budget / (stop_dist * point_val)

        rounded_size = self._apply_rounding(raw_size, asset_class, state)

        state.raw_position_size = raw_size
        state.rounded_position_size = rounded_size
        state.cost_adjusted_position_size = rounded_size
        state.final_position_size = rounded_size

        status = "PASS"
        reason = f"Raw size = {raw_size:,.4f}, Rounded size = {rounded_size:,.4f} ({asset_class})"

        msg = f"Asset = {asset_class}, Budget = ${budget:,.2f}, Stop Dist = {stop_dist:,.5f} -> Raw = {raw_size:,.4f}, Rounded = {rounded_size:,.4f}"
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
