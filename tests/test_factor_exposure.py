"""
Unit tests for Module 7 — Factor Exposure.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.factor_exposure import FactorExposureModule


class TestFactorExposureModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.pos1 = Position(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            quantity=1.0,
            entry_price=1.0850,
            current_price=1.0870,
            stop_price=1.0820,
            monetary_risk_at_stop=300.0,
            strategy_id="fx_trend",
        )
        self.pos2 = Position(
            symbol="GBPUSD",
            asset_class="forex",
            side="long",
            quantity=1.0,
            entry_price=1.2700,
            current_price=1.2720,
            stop_price=1.2650,
            monetary_risk_at_stop=500.0,
            strategy_id="fx_trend",
        )
        self.trade = TradeCandidate(
            symbol="AUDUSD",
            asset_class="forex",
            side="long",
            entry_price=0.6500,
            proposed_stop_price=0.6450,
            strategy_id="fx_trend",
        )
        self.module = FactorExposureModule()

    def test_multi_pair_usd_factor_exposure_rejection(self):
        """
        EURUSD long + GBPUSD long + AUDUSD long -> net USD exposure = -3.0. Limit USD = 2.0. Should REJECT.
        """
        config = CapitalManagementConfig(factor_limits={"USD": 2.0, "EUR": 2.0, "GBP": 2.0, "AUD": 2.0})
        state = CapitalManagementState(
            account=self.account,
            portfolio=[self.pos1, self.pos2],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            governed_risk_budget=500.0,
            permitted_risk_budget=500.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.current_factor_exposure["USD"], -2.0)
        self.assertEqual(updated.projected_factor_exposure["USD"], -3.0)
        self.assertEqual(updated.factor_constraint_status, "REJECT")
        self.assertEqual(updated.module_results["factor_check"].status, "REJECT")
        self.assertIn("USD factor exposure", updated.rejection_reasons[0])

    def test_factor_exposure_pass(self):
        """
        USD limit = 4.0. Should PASS.
        """
        config = CapitalManagementConfig(factor_limits={"USD": 4.0, "EUR": 2.0, "GBP": 2.0, "AUD": 2.0})
        state = CapitalManagementState(
            account=self.account,
            portfolio=[self.pos1, self.pos2],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            governed_risk_budget=500.0,
            permitted_risk_budget=500.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.factor_constraint_status, "PASS")
        self.assertEqual(updated.module_results["factor_check"].status, "PASS")


if __name__ == "__main__":
    unittest.main()
