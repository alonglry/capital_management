"""
Unit tests for TransactionCostModule.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.transaction_cost import TransactionCostModule


class TestTransactionCostModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=80000.0, currency="USD")
        self.config = CapitalManagementConfig(slippage_unit="price")

    def test_cost_calculation(self):
        trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=145.0,
            spread=0.05,
            commission=0.10,
            expected_slippage=0.10,
            strategy_id="momentum",
        )
        inst = InstrumentSpec.create_default("AAPL", "equity")
        inst.metadata_verified = True
        inst.metadata_source = "explicit_test"

        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            instrument=inst,
            governed_risk_budget=500.0,
            permitted_risk_budget=500.0,
            stop_distance=5.0,
            monetary_risk_per_unit=5.0,
            rounded_position_size=100.0,
            executable_position_size=100.0,
        )
        module = TransactionCostModule()
        updated = module.process(state)

        # Spread cost = 0.05 * 100 = $5.00
        # Commission cost = 0.10 * 100 = $10.00
        # Slippage cost = 0.10 * 100 = $10.00
        # Total transaction cost = $25.00
        self.assertEqual(updated.estimated_spread_cost, 5.0)
        self.assertEqual(updated.estimated_commission, 10.0)
        self.assertEqual(updated.estimated_slippage, 10.0)
        self.assertEqual(updated.total_transaction_cost, 25.0)


if __name__ == "__main__":
    unittest.main()
