"""
Module 9 — Stop-Loss Risk Calculation.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class StopRiskModule(BaseRiskModule):
    """
    Module 9: Calculates stop distance and monetary risk per unit using InstrumentSpec in account currency.
    """

    @property
    def name(self) -> str:
        return "stop_risk"

    @property
    def module_type(self) -> str:
        return "calculation"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "entry_price": state.trade.entry_price,
            "proposed_stop_price": state.trade.proposed_stop_price,
            "side": state.trade.side,
            "asset_class": state.trade.asset_class,
            "account_currency": state.account.currency,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "stop_distance": state.stop_distance,
            "stop_distance_pct": state.stop_distance_pct,
            "monetary_risk_per_unit": state.monetary_risk_per_unit,
            "stop_method": state.stop_method,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        entry = state.trade.entry_price
        stop = state.trade.proposed_stop_price

        # 1. Require explicit InstrumentSpec
        inst = state.instrument
        if inst is None:
            state.add_rejection("Missing required explicit InstrumentSpec metadata.")
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason="Missing required explicit InstrumentSpec metadata.",
            )
            return state

        # 2. Validate InstrumentSpec for capital management
        is_valid_spec, msg_spec = inst.validate_for_capital_management(state.account.currency, state.trade)
        if not is_valid_spec and state.config.require_verified_instrument_metadata == "reject":
            state.add_rejection(f"Instrument validation failed: {msg_spec}")
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason=f"Instrument validation error: {msg_spec}",
            )
            return state

        # 3. Validate stop direction
        is_valid_stop_dir, msg_stop_dir = state.trade.validate_stop_direction()
        if not is_valid_stop_dir:
            state.add_rejection(msg_stop_dir)
            status = "REJECT"
            reason = msg_stop_dir
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status=status,
                reason=reason,
            )
            return state

        if entry <= 0 or not math.isfinite(entry):
            state.add_rejection(f"Trade candidate entry_price ({entry}) must be > 0 and finite.")
            status = "REJECT"
            reason = f"Invalid entry_price ({entry})"
        else:
            dist = abs(entry - stop)
            dist_pct = dist / entry

            state.stop_distance = dist
            state.stop_distance_pct = dist_pct
            state.stop_method = "price"

            if dist <= 0 or not math.isfinite(dist):
                status = "REJECT"
                reason = f"Proposed stop price equals or exceeds entry price (stop_distance = {dist})"
                state.add_rejection(reason)
            else:
                pip_val = state.trade.pip_value_per_lot
                pip_ccy = state.trade.pip_value_currency
                try:
                    monetary_risk_per_unit = inst.calculate_monetary_risk_per_unit(
                        entry_price=entry,
                        stop_price=stop,
                        pip_value_per_lot=pip_val,
                        pip_value_currency=pip_ccy,
                        account_currency=state.account.currency,
                        fx_rates=state.market_data.fx_rates,
                    )
                except ValueError as err:
                    state.add_rejection(str(err))
                    status = "REJECT"
                    reason = str(err)
                    state.module_results[self.name] = ModuleResult(
                        module_name=self.name,
                        enabled=True,
                        input_summary=self._get_input_summary(state),
                        output_summary=self._get_output_summary(state),
                        status=status,
                        reason=reason,
                    )
                    return state

                if not math.isfinite(monetary_risk_per_unit) or monetary_risk_per_unit <= 0:
                    status = "REJECT"
                    reason = f"Calculated invalid monetary risk per unit (${monetary_risk_per_unit})"
                    state.add_rejection(reason)
                else:
                    state.monetary_risk_per_unit = monetary_risk_per_unit
                    status = "PASS"
                    reason = f"Calculated stop distance = {dist:,.5f} ({dist_pct:.2%}), monetary risk per unit = ${monetary_risk_per_unit:,.4f} ({state.account.currency})"

        msg = f"Entry = {entry}, Stop = {stop}, Stop Distance = {state.stop_distance:,.5f} ({state.stop_distance_pct:.2%}), Risk/Unit = ${state.monetary_risk_per_unit:,.4f}, Status = {status}"
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
