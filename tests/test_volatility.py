"""
Unit tests for Module 3 — Volatility Governor.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.volatility_governor import VolatilityGovernorModule


class TestVolatilityGovernorModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=75000.0)
        self.config = CapitalManagementConfig()
        self.module = VolatilityGovernorModule()

    def _create_state(self, atr_ratio: float) -> CapitalManagementState:
        trade = TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0820,
            strategy_id="momentum",
            atr_ratio=atr_ratio,
        )
        return CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            adjusted_risk_budget=500.0,
        )

    def test_atr_ratio_tiers(self):
        # ATR Ratio = 0.5 -> Tier 0.0-0.7 -> Multiplier 0.75 -> Budget 375.0
        state = self._create_state(0.5)
        updated = self.module.process(state)
        self.assertEqual(updated.volatility_multiplier, 0.75)
        self.assertEqual(updated.adjusted_risk_budget, 375.0)

        # ATR Ratio = 1.0 -> Tier 0.7-1.3 -> Multiplier 1.00 -> Budget 500.0
        state = self._create_state(1.0)
        updated = self.module.process(state)
        self.assertEqual(updated.volatility_multiplier, 1.00)
        self.assertEqual(updated.adjusted_risk_budget, 500.0)

        # ATR Ratio = 1.5 -> Tier 1.3-1.8 -> Multiplier 0.75 -> Budget 375.0
        state = self._create_state(1.5)
        updated = self.module.process(state)
        self.assertEqual(updated.volatility_multiplier, 0.75)
        self.assertEqual(updated.adjusted_risk_budget, 375.0)

        # ATR Ratio = 2.0 -> Tier > 1.8 -> Multiplier 0.50 -> Budget 250.0
        state = self._create_state(2.0)
        updated = self.module.process(state)
        self.assertEqual(updated.volatility_multiplier, 0.50)
        self.assertEqual(updated.adjusted_risk_budget, 250.0)

    def test_disabled_module(self):
        self.config.modules["volatility_governor"] = False
        state = self._create_state(2.0)
        updated = self.module.process(state)
        self.assertEqual(updated.adjusted_risk_budget, 500.0)
        self.assertEqual(updated.module_results["volatility_governor"].status, "SKIPPED")


if __name__ == "__main__":
    unittest.main()
