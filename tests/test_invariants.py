"""
Property-based and Invariant Tests for Capital Management Engine (Part 27).
"""

import unittest

from capital_management.models import (
    AccountState,
    CapitalManagementConfig,
    MarketData,
    Position,
    TradeCandidate,
)
from capital_management.pipeline import CapitalManagementPipeline


class TestCapitalEngineInvariants(unittest.TestCase):

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
        self.pipeline = CapitalManagementPipeline()

    def test_invariant_1_actual_total_risk_le_permitted_risk_budget(self):
        """
        Invariant 1: actual_total_risk <= permitted_risk_budget after ALL sizing, rounding, and cost calculations.
        """
        result = self.pipeline.run(account=self.account, portfolio=[], trade=self.trade)
        if result.approved:
            self.assertLessEqual(result.actual_total_risk, result.permitted_risk_budget + 1e-4)

    def test_invariant_2_executable_position_size_le_raw_position_size(self):
        """
        Invariant 2: executable_position_size <= raw_position_size when quantity rounding is risk-constrained.
        """
        result = self.pipeline.run(account=self.account, portfolio=[], trade=self.trade)
        if result.approved:
            self.assertLessEqual(result.executable_position_size, result.raw_position_size + 1e-6)

    def test_invariant_3_positive_risk_trade_cannot_reduce_portfolio_heat(self):
        """
        Invariant 3: Adding a positive-risk trade cannot reduce portfolio heat.
        """
        pos = Position(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            quantity=100,
            entry_price=300.0,
            current_price=310.0,
            stop_price=280.0,
            monetary_risk_at_stop=2000.0,
            strategy_id="trend",
        )
        result = self.pipeline.run(account=self.account, portfolio=[pos], trade=self.trade)
        self.assertGreaterEqual(result.projected_portfolio_heat, result.current_portfolio_heat)

    def test_invariant_4_disabling_risk_reducing_module_must_not_reduce_risk(self):
        """
        Invariant 4: Disabling a risk-reducing module (e.g. Drawdown Governor) must not accidentally reduce permitted risk.
        """
        account_dd = AccountState(equity=90000.0, cash=50000.0, peak_equity=100000.0)

        # Enabled drawdown governor
        res_enabled = self.pipeline.run(account=account_dd, portfolio=[], trade=self.trade)

        # Disabled drawdown governor
        cfg_disabled = CapitalManagementConfig()
        cfg_disabled.modules["drawdown_governor"] = False
        res_disabled = self.pipeline.run(account=account_dd, portfolio=[], trade=self.trade, config=cfg_disabled)

        self.assertGreaterEqual(res_disabled.permitted_risk_budget, res_enabled.permitted_risk_budget)

    def test_invariant_5_increasing_permitted_risk_never_reduces_raw_position_size(self):
        """
        Invariant 5: Increasing permitted risk must never result in a smaller theoretical position size.
        """
        trade1 = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, strategy_id="t1"
        )
        cfg1 = CapitalManagementConfig(base_risk_pct=0.005)
        cfg2 = CapitalManagementConfig(base_risk_pct=0.010)

        res1 = self.pipeline.run(account=self.account, portfolio=[], trade=trade1, config=cfg1)
        res2 = self.pipeline.run(account=self.account, portfolio=[], trade=trade1, config=cfg2)

        self.assertGreaterEqual(res2.raw_position_size, res1.raw_position_size)

    def test_invariant_6_increasing_stop_distance_never_increases_position_size(self):
        """
        Invariant 6: Increasing stop distance must never increase position size.
        """
        trade_small_stop = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, strategy_id="t1"
        )
        trade_large_stop = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=135.0, strategy_id="t1"
        )

        res_small = self.pipeline.run(account=self.account, portfolio=[], trade=trade_small_stop)
        res_large = self.pipeline.run(account=self.account, portfolio=[], trade=trade_large_stop)

        self.assertLessEqual(res_large.raw_position_size, res_small.raw_position_size)

    def test_invariant_7_increasing_transaction_costs_never_increases_executable_size(self):
        """
        Invariant 7: Increasing transaction costs must never increase executable position size.
        """
        trade_low_cost = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, commission=0.01, strategy_id="t1"
        )
        trade_high_cost = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, commission=1.00, strategy_id="t1"
        )

        res_low = self.pipeline.run(account=self.account, portfolio=[], trade=trade_low_cost)
        res_high = self.pipeline.run(account=self.account, portfolio=[], trade=trade_high_cost)

        self.assertLessEqual(res_high.executable_position_size, res_low.executable_position_size)

    def test_invariant_8_increasing_correlation_never_increases_correlation_capacity(self):
        """
        Invariant 8: Increasing portfolio correlation with existing positions must never increase correlation risk capacity.
        """
        pos = Position(
            symbol="MSFT", asset_class="equity", side="long", quantity=100, entry_price=300.0, current_price=310.0, stop_price=280.0, monetary_risk_at_stop=2000.0, strategy_id="t1"
        )
        trade = TradeCandidate(
            symbol="NVDA", asset_class="equity", side="long", entry_price=400.0, proposed_stop_price=380.0, strategy_id="t1"
        )

        m_low = MarketData(correlation_matrix={"MSFT": {"MSFT": 1.0, "NVDA": 0.20}, "NVDA": {"MSFT": 0.20, "NVDA": 1.0}})
        m_high = MarketData(correlation_matrix={"MSFT": {"MSFT": 1.0, "NVDA": 0.85}, "NVDA": {"MSFT": 0.85, "NVDA": 1.0}})

        res_low = self.pipeline.run(account=self.account, portfolio=[pos], trade=trade, market_data=m_low)
        res_high = self.pipeline.run(account=self.account, portfolio=[pos], trade=trade, market_data=m_high)

        self.assertLessEqual(res_high.correlation_risk_capacity, res_low.correlation_risk_capacity + 1e-4)


if __name__ == "__main__":
    unittest.main()
