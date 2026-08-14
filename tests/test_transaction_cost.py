"""
Unit tests for Module 10 — Transaction Cost Adjustment.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.transaction_cost import TransactionCostModule


class TestTransactionCostModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.config = CapitalManagementConfig()
        self.module = TransactionCostModule()

    def test_cost_adjustment_reduces_size(self):
        trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=100.0,
            proposed_stop_price=95.0,
            commission=0.10,  # $0.10 per share
            spread=0.05,  # $0.05 spread
            expected_slippage=0.001,  # 0.1% slippage = $0.10 per share
            strategy_id="momentum",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            adjusted_risk_budget=500.0,
            stop_distance=5.0,
            rounded_position_size=100.0,
        )
        updated = self.module.process(state)
        # Total cost per share = $5.0 (stop) + $0.05 (spread) + $0.10 (comm) + $0.10 (slip) = $5.25
        # 500 / 5.25 = 95.23 shares -> floor_int = 95 shares.
        self.assertTrue(updated.total_transaction_cost > 0)
        self.assertEqual(updated.cost_adjusted_position_size, 95.0)
        self.assertEqual(updated.final_position_size, 95.0)


if __name__ == "__main__":
    unittest.main()
