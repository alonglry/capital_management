"""
Module 11 — Transaction Cost Calculation.
"""

from typing import Any, Dict

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


class TransactionCostModule(BaseRiskModule):
    """
    Module 11: Calculates transaction costs (spread, commission, slippage) based on executable_position_size.

    Supports explicit slippage units: 'price', 'pips', 'percentage'.
    """

    @property
    def name(self) -> str:
        return "transaction_cost"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "spread": state.trade.spread,
            "commission": state.trade.commission,
            "expected_slippage": state.trade.expected_slippage,
            "slippage_unit": state.config.slippage_unit,
            "executable_position_size": state.executable_position_size,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "estimated_spread_cost": state.estimated_spread_cost,
            "estimated_commission": state.estimated_commission,
            "estimated_slippage": state.estimated_slippage,
            "total_transaction_cost": state.total_transaction_cost,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        size = state.executable_position_size
        entry = state.trade.entry_price
        defaults = state.config.transaction_cost_assumptions

        if state.instrument is None:
            state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)
        inst = state.instrument

        spread = state.trade.spread if state.trade.spread is not None else defaults.get("default_spread", 0.0)
        comm = state.trade.commission if state.trade.commission is not None else defaults.get("default_commission", 0.0)
        slip = state.trade.expected_slippage if state.trade.expected_slippage is not None else defaults.get("default_slippage", 0.0)
        slip_unit = state.config.slippage_unit.lower()

        # 1. Spread cost
        ac = inst.asset_class.upper()
        if ac == "FOREX" and state.trade.pip_value_per_lot and state.trade.pip_value_per_lot > 0:
            pip_val = state.trade.pip_value_per_lot
            pip_size = inst.pip_size
            spread_pips = spread / pip_size if spread > 0 else 0.0
            spread_cost_unit = spread_pips * pip_val
        else:
            spread_cost_unit = spread * inst.point_value * inst.contract_size

        # 2. Commission cost
        comm_cost_unit = comm

        # 3. Slippage cost conversion based on explicit unit
        if slip_unit == "pips":
            pip_size = inst.pip_size
            if ac == "FOREX" and state.trade.pip_value_per_lot and state.trade.pip_value_per_lot > 0:
                slip_cost_unit = slip * state.trade.pip_value_per_lot
            else:
                slip_cost_unit = (slip * pip_size) * inst.point_value * inst.contract_size
        elif slip_unit == "price":
            slip_cost_unit = slip * inst.point_value * inst.contract_size
        else:  # 'percentage'
            slip_cost_unit = (slip * entry) * inst.point_value * inst.contract_size

        spread_cost = spread_cost_unit * size
        comm_cost = comm_cost_unit * size
        slip_cost = slip_cost_unit * size
        total_tx_cost = spread_cost + comm_cost + slip_cost

        state.estimated_spread_cost = spread_cost
        state.estimated_commission = comm_cost
        state.estimated_slippage = slip_cost
        state.total_transaction_cost = total_tx_cost
        state.actual_transaction_cost = total_tx_cost

        status = "PASS"
        reason = f"Calculated actual transaction costs = ${total_tx_cost:,.2f} for size {size}"

        msg = f"Spread = ${spread_cost:,.2f}, Comm = ${comm_cost:,.2f}, Slip({slip_unit}) = ${slip_cost:,.2f} -> Total Tx Cost = ${total_tx_cost:,.2f}"
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
