"""
Unit tests for Module 5 — Portfolio Heat.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.portfolio_heat import PortfolioHeatModule


class TestPortfolioHeatModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.positions = [
            Position(
                symbol="MSFT",
                asset_class="equity",
                side="long",
                quantity=100,
                entry_price=300.0,
                current_price=310.0,
                stop_price=275.0,
                monetary_risk_at_stop=2500.0,
                strategy_id="momentum",
            ),
            Position(
                symbol="NVDA",
                asset_class="equity",
                side="long",
                quantity=50,
                entry_price=400.0,
                current_price=420.0,
                stop_price=360.0,
                monetary_risk_at_stop=2000.0,
                strategy_id="breakout",
            ),
        ]  # Total current risk = 2500 + 2000 = 4500 (4.5%)
        self.trade = TradeCandidate(
            symbol="AMD",
            asset_class="equity",
            side="long",
            entry_price=100.0,
            proposed_stop_price=90.0,
            strategy_id="breakout",
        )
        self.module = PortfolioHeatModule()

    def test_heat_exceeded_reject_policy(self):
        config = CapitalManagementConfig(max_portfolio_heat_pct=0.05, heat_policy="reject")
        state = CapitalManagementState(
            account=self.account,
            portfolio=self.positions,
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            adjusted_risk_budget=1000.0,  # 1% risk -> 4.5% + 1% = 5.5% > 5.0%
        )
        updated = self.module.process(state)
        self.assertEqual(updated.current_portfolio_heat, 0.045)
        self.assertEqual(updated.module_results["portfolio_heat"].status, "REJECT")
        self.assertIn("portfolio heat", updated.rejection_reasons[0].lower())

    def test_heat_exceeded_reduce_policy(self):
        config = CapitalManagementConfig(max_portfolio_heat_pct=0.05, heat_policy="reduce")
        state = CapitalManagementState(
            account=self.account,
            portfolio=self.positions,
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            adjusted_risk_budget=1000.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.current_portfolio_heat, 0.045)
        self.assertEqual(updated.adjusted_risk_budget, 500.0)  # Reduced to fill remaining 0.5% ($500)
        self.assertEqual(updated.projected_portfolio_heat, 0.05)
        self.assertEqual(updated.module_results["portfolio_heat"].status, "PASS")


if __name__ == "__main__":
    unittest.main()
