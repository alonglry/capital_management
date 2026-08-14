"""
Unit tests for Module 8 — Stop-Loss Risk Calculation.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.stop_risk import StopRiskModule


class TestStopRiskModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.config = CapitalManagementConfig()
        self.module = StopRiskModule()

    def test_valid_stop_distance(self):
        trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=145.0,
            strategy_id="momentum",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.stop_distance, 5.0)
        self.assertAlmostEqual(updated.stop_distance_pct, 5.0 / 150.0, places=5)
        self.assertEqual(updated.module_results["stop_risk"].status, "PASS")

    def test_zero_stop_distance_rejection(self):
        trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=150.0,
            strategy_id="momentum",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.stop_distance, 0.0)
        self.assertEqual(updated.module_results["stop_risk"].status, "REJECT")
        self.assertIn("stop_distance <= 0", updated.rejection_reasons[0])


if __name__ == "__main__":
    unittest.main()
