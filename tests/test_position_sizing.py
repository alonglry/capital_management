"""
Unit tests for Module 9 — Position Sizing.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.position_sizing import PositionSizingModule


class TestPositionSizingModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.config = CapitalManagementConfig()
        self.module = PositionSizingModule()

    def test_equity_position_sizing(self):
        trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=100.0,
            proposed_stop_price=94.70,  # stop distance = 5.30
            strategy_id="trend",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            governed_risk_budget=500.0,
            permitted_risk_budget=500.0,
            stop_distance=5.30,
            monetary_risk_per_unit=5.30,
        )
        # Raw shares = 500 / 5.30 = 94.3396. Rounding = floor_int -> 94 shares.
        updated = self.module.process(state)
        self.assertAlmostEqual(updated.raw_position_size, 500.0 / 5.30, places=4)
        self.assertEqual(updated.rounded_position_size, 94.0)
        self.assertEqual(updated.final_position_size, 94.0)

    def test_forex_position_sizing(self):
        trade = TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0820,  # 30 pips
            pip_value_per_lot=10.0,
            strategy_id="fx_trend",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=self.config,
            governed_risk_budget=300.0,
            permitted_risk_budget=300.0,
            stop_distance=0.0030,
            monetary_risk_per_unit=300.0,
        )
        # 300 / (30 * 10) = 1.0 lot.
        updated = self.module.process(state)
        self.assertEqual(updated.raw_position_size, 1.0)
        self.assertEqual(updated.rounded_position_size, 1.0)


if __name__ == "__main__":
    unittest.main()
