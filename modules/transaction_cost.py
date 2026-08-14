"""
Module 10 — Transaction Cost Adjustment.
"""

from typing import Any, Dict

from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.position_sizing import PositionSizingModule


class TransactionCostModule(BaseRiskModule):
    """
    Module 10: Calculates transaction costs (spread, commission, slippage) and adjusts position size
    so that total monetary risk + transaction costs <= allowed risk budget.
    """

    @property
    def name(self) -> str:
        return "transaction_cost"

    def _get_input_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "spread": state.trade.spread,
            "commission": state.trade.commission,
            "expected_slippage": state.trade.expected_slippage,
            "position_size": state.rounded_position_size,
        }

    def _get_output_summary(self, state: CapitalManagementState) -> Dict[str, Any]:
        return {
            "estimated_spread_cost": state.estimated_spread_cost,
            "estimated_commission": state.estimated_commission,
            "estimated_slippage": state.estimated_slippage,
            "total_transaction_cost": state.total_transaction_cost,
            "cost_adjusted_position_size": state.cost_adjusted_position_size,
        }

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        size = state.rounded_position_size
        budget = state.adjusted_risk_budget
        stop_dist = state.stop_distance
        entry = state.trade.entry_price
        defaults = state.config.transaction_cost_assumptions

        spread = state.trade.spread if state.trade.spread is not None else defaults.get("default_spread", 0.0)
        comm = state.trade.commission if state.trade.commission is not None else defaults.get("default_commission", 0.0)
        slip = state.trade.expected_slippage if state.trade.expected_slippage is not None else defaults.get("default_slippage", 0.0)

        # Cost per unit calculation
        point_val = state.trade.point_value or 1.0
        if state.trade.asset_class.lower() == "forex" and state.trade.pip_value_per_lot:
            pip_val = state.trade.pip_value_per_lot
            pip_size = 0.01 if "JPY" in state.trade.symbol.upper() else 0.0001
            pips = stop_dist / pip_size
            risk_loss_per_lot = pips * pip_val
            spread_pips = spread / pip_size if spread > 0 else 0.0
            spread_cost_per_lot = spread_pips * pip_val
            comm_per_lot = comm
            slip_cost_per_lot = slip * entry * (100000.0 if state.trade.lot_size is None else state.trade.lot_size)

            spread_cost = spread_cost_per_lot * size
            comm_cost = comm_per_lot * size
            slip_cost = slip_cost_per_lot * size
            total_unit_cost = risk_loss_per_lot + spread_cost_per_lot + comm_per_lot + slip_cost_per_lot

            if total_unit_cost > 0:
                adjusted_raw = budget / total_unit_cost
            else:
                adjusted_raw = size
        else:
            risk_loss_per_unit = stop_dist * point_val
            spread_cost_per_unit = spread * point_val
            comm_cost_per_unit = comm
            slip_cost_per_unit = slip * entry

            spread_cost = spread_cost_per_unit * size
            comm_cost = comm_cost_per_unit * size
            slip_cost = slip_cost_per_unit * size

            total_cost_per_unit = risk_loss_per_unit + spread_cost_per_unit + comm_cost_per_unit + slip_cost_per_unit

            if total_cost_per_unit > 0:
                adjusted_raw = budget / total_cost_per_unit
            else:
                adjusted_raw = size

        total_tx_cost = spread_cost + comm_cost + slip_cost
        state.estimated_spread_cost = spread_cost
        state.estimated_commission = comm_cost
        state.estimated_slippage = slip_cost
        state.total_transaction_cost = total_tx_cost

        # Apply rounding to cost adjusted size
        sizer = PositionSizingModule()
        adjusted_rounded = sizer._apply_rounding(adjusted_raw, state.trade.asset_class, state)

        state.cost_adjusted_position_size = adjusted_rounded
        state.final_position_size = adjusted_rounded

        status = "PASS"
        reason = f"Total tx cost = ${total_tx_cost:,.2f}, adjusted size = {adjusted_rounded}"

        msg = f"Spread = ${spread_cost:,.2f}, Comm = ${comm_cost:,.2f}, Slip = ${slip_cost:,.2f} -> Total Tx Cost = ${total_tx_cost:,.2f}, Adjusted Size = {adjusted_rounded}"
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
