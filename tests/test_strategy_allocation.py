"""
Unit tests for Module 4 — Strategy Allocation.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.strategy_allocation import StrategyAllocationModule


class TestStrategyAllocationModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=75000.0)
        self.config = CapitalManagementConfig(
            strategy_allocations={"momentum": 0.75, "carry": 0.50, "default": 1.0}
        )
        self.module = StrategyAllocationModule()

    def test_strategy_allocation_carry(self):
        trade = TradeCandidate(
            symbol="USDJPY",
            asset_class="forex",
            side="long",
            entry_price=145.0,
            proposed_stop_price=144.0,
            strategy_id="carry",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            adjusted_risk_budget=500.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.strategy_multiplier, 0.50)
        self.assertEqual(updated.adjusted_risk_budget, 250.0)

    def test_disabled_module(self):
        self.config.modules["strategy_allocation"] = False
        trade = TradeCandidate(
            symbol="USDJPY",
            asset_class="forex",
            side="long",
            entry_price=145.0,
            proposed_stop_price=144.0,
            strategy_id="carry",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            adjusted_risk_budget=500.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.adjusted_risk_budget, 500.0)
        self.assertEqual(updated.module_results["strategy_allocation"].status, "SKIPPED")


if __name__ == "__main__":
    unittest.main()
