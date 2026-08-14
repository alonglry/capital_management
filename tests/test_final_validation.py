"""
Unit tests for Module 12 — Final Risk Validation.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.final_validation import FinalValidationModule


class TestFinalValidationModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0)
        self.trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=100.0,
            proposed_stop_price=95.0,
            strategy_id="momentum",
        )
        self.config = CapitalManagementConfig()
        self.module = FinalValidationModule()

    def test_final_validation_pass(self):
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
            instrument=InstrumentSpec.create_default("AAPL", "equity"),
            governed_risk_budget=500.0,
            permitted_risk_budget=500.0,
            stop_distance=5.0,
            monetary_risk_per_unit=5.0,
            executable_position_size=100.0,
            final_position_size=100.0,
            actual_stop_loss_risk=500.0,
            actual_transaction_cost=0.0,
            actual_total_risk=500.0,
            projected_portfolio_heat=0.005,
            projected_correlation_adjusted_risk=0.005,
            stress_loss=500.0,
        )
        updated = self.module.process(state)
        self.assertTrue(updated.approved)
        self.assertEqual(len(updated.rejection_reasons), 0)
        self.assertEqual(updated.module_results["final_validation"].status, "PASS")

    def test_final_validation_reject_zero_size(self):
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=self.config,
            stop_distance=5.0,
            final_position_size=0.0,
        )
        updated = self.module.process(state)
        self.assertFalse(updated.approved)
        self.assertTrue(len(updated.rejection_reasons) > 0)
        self.assertIn("zero or negative", updated.rejection_reasons[0].lower())


if __name__ == "__main__":
    unittest.main()
