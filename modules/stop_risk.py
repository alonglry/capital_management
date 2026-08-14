"""
Module 9 — Stop-Loss Risk Calculation.
"""

import math
from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
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

        # 1. Resolve or create InstrumentSpec
        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)

        inst = state.instrument

        # 2. Check metadata source safety
        if getattr(inst, "instrument_metadata_source", "explicit") == "legacy_default":
            # If policy requires explicit/verified metadata, verify trade or market_data supplies conversion details
            has_independent_info = (
                state.trade.point_value is not None or state.trade.pip_value_per_lot is not None
            )
            if getattr(state.config, "require_verified_instrument_metadata", "reject") == "reject" and not has_independent_info:
                # If neither point_value nor pip_value_per_lot was passed and it's legacy_default for forex or complex equity
                if inst.asset_class.upper() == "FOREX" and inst.quote_currency != state.account.currency and not state.market_data.fx_rates:
                    state.add_rejection(
                        f"Unsafe InstrumentSpec default for '{state.trade.symbol}': monetary conversion parameters cannot be independently verified."
                    )
                    status = "REJECT"
                    reason = "Unsafe legacy_default InstrumentSpec without independent verification"
                    state.module_results[self.name] = ModuleResult(
                        module_name=self.name,
                        enabled=True,
                        input_summary=self._get_input_summary(state),
                        output_summary=self._get_output_summary(state),
                        status=status,
                        reason=reason,
                    )
                    return state

        # 3. Validate broker quantity rules early
        is_valid_broker, msg_broker = inst.validate_broker_rules()
        if not is_valid_broker:
            state.add_rejection(f"Invalid broker quantity rules for '{inst.symbol}': {msg_broker}")
            status = "REJECT"
            reason = f"Broker rule error: {msg_broker}"
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status=status,
                reason=reason,
            )
            return state

        # 4. Validate stop direction
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

        if entry <= 0 or math.isnan(entry) or math.isinf(entry):
            state.add_rejection(f"Trade candidate entry_price ({entry}) must be > 0 and finite.")
            status = "REJECT"
            reason = f"Invalid entry_price ({entry})"
        else:
            dist = abs(entry - stop)
            dist_pct = dist / entry

            state.stop_distance = dist
            state.stop_distance_pct = dist_pct
            state.stop_method = "price"

            if dist <= 0 or math.isnan(dist) or math.isinf(dist):
                status = "REJECT"
                reason = f"Proposed stop price equals or exceeds entry price (stop_distance = {dist})"
                state.add_rejection(reason)
            else:
                pip_val = state.trade.pip_value_per_lot
                try:
                    monetary_risk_per_unit = inst.calculate_monetary_risk_per_unit(
                        entry_price=entry,
                        stop_price=stop,
                        pip_value_per_lot=pip_val,
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

                if math.isnan(monetary_risk_per_unit) or math.isinf(monetary_risk_per_unit) or monetary_risk_per_unit <= 0:
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
