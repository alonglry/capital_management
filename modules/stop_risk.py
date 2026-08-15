"""
Module 9 — Stop-Loss Risk Calculation.
"""

import math
from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.models.trade_candidate import resolve_effective_stop_price
from capital_management.modules.base_module import BaseRiskModule


class StopRiskModule(BaseRiskModule):
    """
    Module 9: Calculates stop distance and monetary risk per unit using InstrumentSpec in account currency,
    resolving effective stop price via resolve_effective_stop_price canonical resolution.
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
            "proposed_stop_price": state.proposed_stop_price,
            "effective_stop_price": state.effective_stop_price,
            "stop_price_source": state.stop_price_source,
            "stop_distance": state.stop_distance,
            "stop_distance_pct": state.stop_distance_pct,
            "monetary_risk_per_unit": state.monetary_risk_per_unit,
            "stop_method": state.stop_method,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        entry = state.trade.entry_price

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

        # 2. Unconditionally validate InstrumentSpec for capital management
        is_valid_spec, msg_spec = inst.validate_for_capital_management(state.account.currency, state.trade)
        if not is_valid_spec:
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

        # 3. Canonical Stop Resolution
        try:
            effective_stop, source, dist = resolve_effective_stop_price(
                state.trade,
                atr=state.trade.atr,
                config=state.config,
            )
        except ValueError as err:
            reason = str(err)
            state.add_rejection(reason)
            state.module_results[self.name] = ModuleResult(
                module_name=self.name,
                enabled=True,
                input_summary=self._get_input_summary(state),
                output_summary=self._get_output_summary(state),
                status="REJECT",
                reason=reason,
            )
            return state

        dist_pct = dist / entry
        state.proposed_stop_price = state.trade.proposed_stop_price
        state.effective_stop_price = effective_stop
        state.stop_price_source = source
        state.stop_distance = dist
        state.stop_distance_pct = dist_pct
        state.stop_method = source

        pip_val = state.trade.pip_value_per_lot
        pip_ccy = state.trade.pip_value_currency
        try:
            monetary_risk_per_unit = inst.calculate_monetary_risk_per_unit(
                entry_price=entry,
                stop_price=effective_stop,
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
            reason = f"Calculated stop distance = {dist:,.5f} ({dist_pct:.2%}), source = '{source}', monetary risk per unit = ${monetary_risk_per_unit:,.4f} ({state.account.currency})"

        msg = f"Entry = {entry}, Effective Stop = {effective_stop} (Source: {source}), Stop Distance = {state.stop_distance:,.5f} ({state.stop_distance_pct:.2%}), Risk/Unit = ${state.monetary_risk_per_unit:,.4f}, Status = {status}"
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
