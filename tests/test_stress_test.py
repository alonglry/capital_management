"""
Unit tests for StressTestModule.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.stress_test import StressTestModule


class TestStressTestModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=80000.0, currency="USD")
        self.trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=140.0,
            strategy_id="momentum",
        )
        self.inst = InstrumentSpec.create_default("AAPL", "equity")
        self.inst.metadata_verified = True
        self.inst.metadata_source = "explicit_test"
        self.module = StressTestModule()

    def test_stress_test_normal_pass(self):
        config = CapitalManagementConfig(
            stress_limits={"gap_pct": 0.01, "extra_slippage_pct": 0.005, "max_stress_risk_pct": 0.05},
            stress_policy="reject",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            instrument=self.inst,
            governed_risk_budget=1000.0,
            permitted_risk_budget=1000.0,
            stop_distance=10.0,
            monetary_risk_per_unit=10.0,
            executable_position_size=100.0,
            final_position_size=100.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.normal_loss, 1000.0)
        # Canonical stressed exit price = 150 * (1 - 0.01) - 0.75 = 147.75. Move = 2.25/share * 100 = 225.0
        self.assertEqual(updated.stress_loss, 225.0)
        self.assertEqual(updated.module_results["stress_test"].status, "PASS")

    def test_stress_test_rejection(self):
        config = CapitalManagementConfig(
            stress_limits={"gap_pct": 0.05, "extra_slippage_pct": 0.02, "max_stress_risk_pct": 0.005},  # max limit $500
            stress_policy="reject",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            instrument=self.inst,
            governed_risk_budget=1000.0,
            permitted_risk_budget=1000.0,
            stop_distance=10.0,
            monetary_risk_per_unit=10.0,
            executable_position_size=100.0,
            final_position_size=100.0,
        )
        updated = self.module.process(state)
        self.assertEqual(updated.module_results["stress_test"].status, "REJECT")

    def test_stress_test_capacity_reduction(self):
        config = CapitalManagementConfig(
            stress_limits={"gap_pct": 0.02, "extra_slippage_pct": 0.01, "max_stress_risk_pct": 0.001},  # max limit $100
            stress_policy="reduce",
        )
        state = CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=self.trade,
            market_data=MarketData(),
            config=config,
            instrument=self.inst,
            governed_risk_budget=1000.0,
            permitted_risk_budget=1000.0,
            stop_distance=10.0,
            monetary_risk_per_unit=10.0,
            executable_position_size=100.0,
            final_position_size=100.0,
        )
        updated = self.module.process(state)
        self.assertTrue(updated.stress_risk_capacity < 1000.0)


if __name__ == "__main__":
    unittest.main()
