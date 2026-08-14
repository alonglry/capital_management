"""
Module 11 — Transaction Cost Calculation.
"""

from typing import Any, Dict, Tuple

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule


def calculate_transaction_cost(
    state: CapitalManagementState, executable_quantity: float
) -> Tuple[float, float, float, float]:
    """
    Canonical transaction cost calculation function computing exact costs from scratch for a given quantity.

    Supports multi-currency fees, one-way/round-trip modes, and explicit units.
    """
    if executable_quantity <= 0:
        return 0.0, 0.0, 0.0, 0.0

    entry = state.trade.entry_price
    defaults = state.config.transaction_cost_assumptions

    inst = state.instrument
    if inst is None:
        return 0.0, 0.0, 0.0, 0.0

    spread = state.trade.spread if state.trade.spread is not None else defaults.get("default_spread", 0.0)
    comm = state.trade.commission if state.trade.commission is not None else defaults.get("default_commission", 0.0)
    slip = state.trade.expected_slippage if state.trade.expected_slippage is not None else defaults.get("default_slippage", 0.0)

    spread_unit = defaults.get("spread_unit", "price").lower()
    spread_mode = defaults.get("spread_cost_mode", "one_way").lower()
    slip_unit = state.config.slippage_unit.lower()
    slip_mode = defaults.get("slippage_cost_mode", "one_way").lower()

    comm_type = defaults.get("commission_type", "per_unit").lower()
    comm_ccy = defaults.get("commission_currency", "account")
    acct_ccy = state.account.currency

    pip_val = state.trade.pip_value_per_lot
    pip_ccy = state.trade.pip_value_currency
    fx_rates = state.market_data.fx_rates

    # 1. Spread Cost
    pip_size_val = inst.pip_size if inst.pip_size is not None else 0.0001
    spread_dist = spread
    if spread_unit == "pips":
        spread_dist = spread * pip_size_val
    elif spread_unit == "percentage":
        spread_dist = spread * entry
    if spread_mode == "round_trip":
        spread_dist *= 2.0

    spread_cost = inst.calculate_loss_for_price_move(
        price_move_distance=spread_dist,
        quantity=executable_quantity,
        account_currency=acct_ccy,
        entry_price=entry,
        pip_value_per_lot=pip_val,
        pip_value_currency=pip_ccy,
        fx_rates=fx_rates,
    )

    # 2. Commission Cost
    comm_currency = acct_ccy if comm_ccy == "account" else comm_ccy
    conv_res = inst.get_fx_conversion(comm_currency, acct_ccy, entry, fx_rates)
    if conv_res is None and comm_currency.upper() != acct_ccy.upper():
        raise ValueError(f"Missing required FX conversion rate from commission currency '{comm_currency}' to account currency '{acct_ccy}'")
    comm_fx_rate = conv_res.conversion_rate if conv_res else 1.0

    if comm_type == "fixed":
        comm_cost = comm * comm_fx_rate
    elif comm_type == "percentage":
        comm_rate = comm
        if comm_rate < 0 or comm_rate >= 1.0:
            raise ValueError(f"Invalid percentage commission_rate ({comm_rate}). Must be 0 <= rate < 1.0")
        notional_val = inst.calculate_notional_value(
            quantity=executable_quantity,
            entry_price=entry,
            account_currency=acct_ccy,
            fx_rates=fx_rates,
        )
        comm_cost = comm_rate * notional_val
    else:  # 'per_unit'
        comm_cost = (comm * executable_quantity) * comm_fx_rate

    # 3. Slippage Cost
    slip_dist = slip
    if slip_unit == "pips":
        slip_dist = slip * pip_size_val
    elif slip_unit == "percentage":
        slip_dist = slip * entry
    if slip_mode == "round_trip":
        slip_dist *= 2.0

    slip_cost = inst.calculate_loss_for_price_move(
        price_move_distance=slip_dist,
        quantity=executable_quantity,
        account_currency=acct_ccy,
        entry_price=entry,
        pip_value_per_lot=pip_val,
        pip_value_currency=pip_ccy,
        fx_rates=fx_rates,
    )

    total_tx_cost = spread_cost + comm_cost + slip_cost
    return spread_cost, comm_cost, slip_cost, total_tx_cost


class TransactionCostModule(BaseRiskModule):
    """
    Module 12: Calculates transaction costs (spread, commission, slippage) based on executable_position_size.
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
