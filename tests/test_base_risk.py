"""
Unit tests for Module 1 — Base Risk Budget.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_risk import BaseRiskModule as BaseRiskBudgetModule


class TestBaseRiskModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=75000.0, currency="USD")
        self.trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=145.0,
            strategy_id="momentum",
        )
        self.config = CapitalManagementConfig(base_risk_pct=0.005)
        self.state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        self.module = BaseRiskBudgetModule()

    def test_base_risk_calculation(self):
        """
        Verify $100,000 * 0.5% = $500 base risk budget.
        """
        updated_state = self.module.process(self.state)
        self.assertEqual(updated_state.base_risk_budget, 500.0)
        self.assertEqual(updated_state.adjusted_risk_budget, 500.0)
        self.assertIn("base_risk", updated_state.module_results)
        self.assertEqual(updated_state.module_results["base_risk"].status, "PASS")

    def test_disabled_module(self):
        """
        Verify enabled=False skips calculation without mutating state.
        """
        self.config.modules["base_risk"] = False
        updated_state = self.module.process(self.state)
        self.assertEqual(updated_state.base_risk_budget, 0.0)
        self.assertEqual(updated_state.adjusted_risk_budget, 0.0)
        self.assertEqual(updated_state.module_results["base_risk"].status, "SKIPPED")
        self.assertFalse(updated_state.module_results["base_risk"].enabled)


if __name__ == "__main__":
    unittest.main()
