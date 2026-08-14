"""
Module 11 — Transaction Cost Calculation.
"""

from typing import Any, Dict, Tuple

from capital_management.models.instrument import InstrumentSpec
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


def calculate_transaction_cost(
    state: CapitalManagementState, executable_quantity: float
) -> Tuple[float, float, float, float]:
    """
    Canonical transaction cost calculation function computing exact costs from scratch for a given quantity.

    Supports linear per-unit costs, fixed order fees, and percentage/notional costs.

    Args:
        state (CapitalManagementState): Shared pipeline state object.
        executable_quantity (float): Target quantity for transaction cost calculation.

    Returns:
        Tuple[float, float, float, float]: (spread_cost, commission_cost, slippage_cost, total_transaction_cost)
    """
    if executable_quantity <= 0:
        return 0.0, 0.0, 0.0, 0.0

    entry = state.trade.entry_price
    defaults = state.config.transaction_cost_assumptions

    if state.instrument is None:
        state.instrument = InstrumentSpec.create_default(state.trade.symbol, state.trade.asset_class)
    inst = state.instrument

    spread = state.trade.spread if state.trade.spread is not None else defaults.get("default_spread", 0.0)
    comm = state.trade.commission if state.trade.commission is not None else defaults.get("default_commission", 0.0)
    slip = state.trade.expected_slippage if state.trade.expected_slippage is not None else defaults.get("default_slippage", 0.0)
    slip_unit = state.config.slippage_unit.lower()
    comm_type = defaults.get("commission_type", "per_unit").lower()

    # Get FX conversion multiplier for native quote currency to account currency
    fx_rate = inst.get_fx_conversion_rate(state.account.currency, entry, state.market_data.fx_rates)
    if fx_rate is None:
        fx_rate = 1.0

    # 1. Spread cost calculation
    ac = inst.asset_class.upper()
    if ac == "FOREX" and state.trade.pip_value_per_lot and state.trade.pip_value_per_lot > 0:
        pip_val = state.trade.pip_value_per_lot
        pip_size = inst.pip_size
        spread_pips = spread / pip_size if spread > 0 else 0.0
        # If quote currency != account currency and pip_val is native
        if inst.quote_currency.upper() != state.account.currency.upper():
            spread_cost = (spread_pips * pip_val * executable_quantity) * fx_rate
        else:
            spread_cost = spread_pips * pip_val * executable_quantity
    else:
        spread_cost = (spread * inst.point_value * inst.contract_size * executable_quantity) * fx_rate

    # 2. Commission cost calculation (per_unit, fixed, percentage)
    if comm_type == "fixed":
        comm_cost = comm * fx_rate
    elif comm_type == "percentage":
        notional_value = executable_quantity * entry * inst.contract_size * inst.point_value
        comm_cost = (comm * notional_value) * fx_rate
    else:  # 'per_unit'
        comm_cost = (comm * executable_quantity) * fx_rate

    # 3. Slippage cost conversion based on explicit unit
    if slip_unit == "pips":
        pip_size = inst.pip_size
        if ac == "FOREX" and state.trade.pip_value_per_lot and state.trade.pip_value_per_lot > 0:
            slip_cost = (slip * state.trade.pip_value_per_lot * executable_quantity)
            if inst.quote_currency.upper() != state.account.currency.upper():
                slip_cost *= fx_rate
        else:
            slip_cost = (slip * pip_size * inst.point_value * inst.contract_size * executable_quantity) * fx_rate
    elif slip_unit == "price":
        slip_cost = (slip * inst.point_value * inst.contract_size * executable_quantity) * fx_rate
    else:  # 'percentage'
        slip_cost = ((slip * entry) * inst.point_value * inst.contract_size * executable_quantity) * fx_rate

    total_tx_cost = spread_cost + comm_cost + slip_cost
    return spread_cost, comm_cost, slip_cost, total_tx_cost


class TransactionCostModule(BaseRiskModule):
    """
    Module 11: Calculates transaction costs (spread, commission, slippage) based on executable_position_size.

    Supports explicit slippage units: 'price', 'pips', 'percentage' and non-linear cost models.
    """

    @property
    def name(self) -> str:
        return "transaction_cost"

    @property
    def module_type(self) -> str:
        return "execution"

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
        spread_cost, comm_cost, slip_cost, total_tx_cost = calculate_transaction_cost(state, size)

        state.estimated_spread_cost = spread_cost
        state.estimated_commission = comm_cost
        state.estimated_slippage = slip_cost
        state.total_transaction_cost = total_tx_cost
        state.actual_transaction_cost = total_tx_cost

        status = "PASS"
        reason = f"Calculated canonical transaction costs = ${total_tx_cost:,.2f} for size {size}"

        msg = f"Spread = ${spread_cost:,.2f}, Comm = ${comm_cost:,.2f}, Slip = ${slip_cost:,.2f} -> Total Tx Cost = ${total_tx_cost:,.2f}"
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
