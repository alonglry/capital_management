"""
Unit tests for Module 2 — Drawdown Governor.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.drawdown_governor import DrawdownGovernorModule


class TestDrawdownGovernorModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=90000.0, cash=65000.0, currency="USD", peak_equity=100000.0)
        self.trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=145.0,
            strategy_id="momentum",
        )
        self.config = CapitalManagementConfig()
        self.state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
            adjusted_risk_budget=500.0,
        )
        self.module = DrawdownGovernorModule()

    def test_drawdown_tier_multiplier(self):
        """
        Verify DD = (100k - 90k)/100k = 10%. Rule min_dd=0.10, max_dd=0.15 has multiplier 0.50.
        Budget should become $500 * 0.50 = $250.
        """
        updated = self.module.process(self.state)
        self.assertEqual(updated.drawdown_multiplier, 0.50)
        self.assertEqual(updated.adjusted_risk_budget, 250.0)
        self.assertEqual(updated.module_results["drawdown_governor"].status, "PASS")

    def test_disabled_module(self):
        """
        Verify enabled=False returns previous budget unchanged and sets multiplier = 1.0.
        """
        self.config.modules["drawdown_governor"] = False
        updated = self.module.process(self.state)
        self.assertEqual(updated.adjusted_risk_budget, 500.0)
        self.assertEqual(updated.module_results["drawdown_governor"].status, "SKIPPED")


if __name__ == "__main__":
    unittest.main()
