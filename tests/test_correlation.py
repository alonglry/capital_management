"""
Unit tests for Module 6 — Correlation-Adjusted Portfolio Risk.
"""

import math
import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.correlation_risk import CorrelationRiskModule


class TestCorrelationRiskModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.pos1 = Position(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            quantity=100,
            entry_price=150.0,
            current_price=155.0,
            stop_price=140.0,
            monetary_risk_at_stop=1000.0,  # 1% equity
            strategy_id="trend",
        )
        self.trade = TradeCandidate(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            entry_price=300.0,
            proposed_stop_price=290.0,
            strategy_id="trend",
        )
        self.module = CorrelationRiskModule()

    def test_correlation_zero(self):
        matrix = {
            "AAPL": {"AAPL": 1.0, "MSFT": 0.0},
            "MSFT": {"AAPL": 0.0, "MSFT": 1.0},
        }
        market_data = MarketData(correlation_matrix=matrix)
        config = CapitalManagementConfig(max_correlation_adjusted_risk_pct=0.04)
        state = CapitalManagementState(
            account=self.account,
            portfolio=[self.pos1],
            trade=self.trade,
            market_data=market_data,
            config=config,
            governed_risk_budget=1000.0,
            permitted_risk_budget=1000.0,  # 1% equity
        )
        # r1 = 0.01, r2 = 0.01, corr = 0 -> sqrt(0.01^2 + 0.01^2) = sqrt(0.0002) = 0.014142 (1.41%)
        updated = self.module.process(state)
        self.assertAlmostEqual(updated.projected_correlation_adjusted_risk, math.sqrt(0.0002), places=5)
        self.assertEqual(updated.module_results["correlation_check"].status, "PASS")

    def test_correlation_one(self):
        matrix = {
            "AAPL": {"AAPL": 1.0, "MSFT": 1.0},
            "MSFT": {"AAPL": 1.0, "MSFT": 1.0},
        }
        market_data = MarketData(correlation_matrix=matrix)
        config = CapitalManagementConfig(max_correlation_adjusted_risk_pct=0.04)
        state = CapitalManagementState(
            account=self.account,
            portfolio=[self.pos1],
            trade=self.trade,
            market_data=market_data,
            config=config,
            governed_risk_budget=1000.0,
            permitted_risk_budget=1000.0,
        )
        # r1 = 0.01, r2 = 0.01, corr = 1 -> sqrt((0.01+0.01)^2) = 0.02 (2.0%)
        updated = self.module.process(state)
        self.assertAlmostEqual(updated.projected_correlation_adjusted_risk, 0.02, places=5)

    def test_missing_correlation_fallback_assume_zero(self):
        market_data = MarketData(correlation_matrix=None)
        config = CapitalManagementConfig(correlation_fallback_policy="assume_zero_correlation")
        state = CapitalManagementState(
            account=self.account,
            portfolio=[self.pos1],
            trade=self.trade,
            market_data=market_data,
            config=config,
            governed_risk_budget=1000.0,
            permitted_risk_budget=1000.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["correlation_check"].status, "PASS")
        self.assertTrue(len(updated.warnings) > 0)


if __name__ == "__main__":
    unittest.main()
