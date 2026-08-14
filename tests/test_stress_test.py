"""
Unit tests for Module 11 — Stress Test.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.stress_test import StressTestModule


class TestStressTestModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.trade = TradeCandidate(
            symbol="TSLA",
            asset_class="equity",
            side="long",
            entry_price=200.0,
            proposed_stop_price=190.0,
            strategy_id="breakout",
        )
        self.module = StressTestModule()

    def test_stress_test_rejection(self):
        # Position size = 100 shares. Normal loss = 100 * 10 = $1,000.
        # Gap 5% ($10/sh -> $1000), extra slippage 2% ($4/sh -> $400) -> Stress loss = $2,400 (2.4%).
        # Stress limit = 2.0% ($2,000). Stress policy = 'reject'.
        config = CapitalManagementConfig(
            stress_limits={"max_stress_risk_pct": 0.02, "gap_pct": 0.05, "extra_slippage_pct": 0.02},
            stress_policy="reject",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            stop_distance=10.0,
            final_position_size=100.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.stress_loss, 2400.0)
        self.assertEqual(updated.module_results["stress_test"].status, "REJECT")
        self.assertIn("exceeds limit", updated.rejection_reasons[0].lower())

    def test_stress_test_reduce_policy(self):
        config = CapitalManagementConfig(
            stress_limits={"max_stress_risk_pct": 0.02, "gap_pct": 0.05, "extra_slippage_pct": 0.02},
            stress_policy="reduce",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            stop_distance=10.0,
            final_position_size=100.0,
        )
        updated = self.module.process(state)
        self.assertTrue(updated.final_position_size < 100.0)
        self.assertEqual(updated.module_results["stress_test"].status, "PASS")


if __name__ == "__main__":
    unittest.main()
