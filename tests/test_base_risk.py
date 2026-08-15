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
        self.assertEqual(updated_state.risk_capital_base, 100000.0)
        self.assertEqual(updated_state.risk_capital_source, "equity")
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

    def test_scenario_equity_100k_cash_100k_uses_equity(self):
        """
        Scenario 1: equity=100000, cash=100000 -> use equity
        """
        account = AccountState(equity=100000.0, cash=100000.0)
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "PASS")
        self.assertEqual(updated.risk_capital_base, 100000.0)
        self.assertEqual(updated.risk_capital_source, "equity")
        self.assertEqual(updated.base_risk_budget, 500.0)
        self.assertEqual(account.equity, 100000.0)  # Verify never mutated

    def test_scenario_equity_none_cash_100k_uses_cash_bootstrap(self):
        """
        Scenario 2: equity=None, cash=100000 -> use cash bootstrap
        """
        account = AccountState(equity=None, cash=100000.0)  # type: ignore
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "PASS")
        self.assertEqual(updated.risk_capital_base, 100000.0)
        self.assertEqual(updated.risk_capital_source, "cash_bootstrap")
        self.assertEqual(updated.base_risk_budget, 500.0)
        self.assertIsNone(account.equity)  # Verify never mutated

    def test_scenario_equity_none_cash_0_rejects(self):
        """
        Scenario 3: equity=None, cash=0 -> REJECT
        """
        account = AccountState(equity=None, cash=0.0)  # type: ignore
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "REJECT")
        self.assertEqual(updated.base_risk_budget, 0.0)
        self.assertEqual(len(updated.rejection_reasons), 1)

    def test_scenario_equity_0_cash_100k_uninitialized_account_bootstraps(self):
        """
        Scenario 4: equity=0, cash=100000, uninitialized account -> bootstrap only if explicitly identified as uninitialized
        """
        account = AccountState(equity=0.0, cash=100000.0, is_initialized=False)
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "PASS")
        self.assertEqual(updated.risk_capital_base, 100000.0)
        self.assertEqual(updated.risk_capital_source, "cash_bootstrap")
        self.assertEqual(updated.base_risk_budget, 500.0)
        self.assertEqual(account.equity, 0.0)  # Never mutated

    def test_scenario_equity_0_cash_100k_open_positions_rejects(self):
        """
        Scenario 5: equity=0, cash=100000, existing open positions -> REJECT data inconsistency
        """
        from capital_management.models.portfolio import Position

        pos = Position(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            quantity=10,
            entry_price=300.0,
            current_price=310.0,
            stop_price=290.0,
            monetary_risk_at_stop=100.0,
            strategy_id="test",
        )
        # Even if is_initialized=False, open positions cause rejection
        account = AccountState(equity=0.0, cash=100000.0, is_initialized=False)
        state = CapitalManagementState(
            account=account,
            portfolio=[pos],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "REJECT")
        self.assertEqual(updated.base_risk_budget, 0.0)
        self.assertTrue(any("data inconsistency" in r for r in updated.rejection_reasons))

    def test_scenario_equity_0_cash_100k_initialized_account_rejects(self):
        """
        Scenario 5b: equity=0, cash=100000, initialized account (default) -> REJECT
        """
        account = AccountState(equity=0.0, cash=100000.0, is_initialized=True)
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "REJECT")
        self.assertEqual(updated.base_risk_budget, 0.0)

    def test_scenario_equity_negative_100_cash_100k_rejects(self):
        """
        Scenario 6: equity=-100, cash=100000 -> REJECT
        """
        account = AccountState(equity=-100.0, cash=100000.0)
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "REJECT")
        self.assertEqual(updated.base_risk_budget, 0.0)
        self.assertTrue(any("negative" in r for r in updated.rejection_reasons))

    def test_scenario_equity_nan_bootstraps_from_cash(self):
        """
        Scenario 7: equity=NaN -> treat as unavailable and bootstrap only from valid cash
        """
        account = AccountState(equity=float("nan"), cash=100000.0)
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "PASS")
        self.assertEqual(updated.risk_capital_base, 100000.0)
        self.assertEqual(updated.risk_capital_source, "cash_bootstrap")
        self.assertEqual(updated.base_risk_budget, 500.0)

    def test_scenario_equity_inf_rejects(self):
        """
        Scenario 8: equity=inf -> REJECT / invalid data
        """
        account = AccountState(equity=float("inf"), cash=100000.0)
        state = CapitalManagementState(
            account=account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["base_risk"].status, "REJECT")
        self.assertEqual(updated.base_risk_budget, 0.0)
        self.assertTrue(any("invalid" in r.lower() or "non-finite" in r.lower() for r in updated.rejection_reasons))


if __name__ == "__main__":
    unittest.main()
