"""
Integration tests for CapitalManagementPipeline.
"""

import unittest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.base_risk import BaseRiskBudgetModule
from capital_management.modules.portfolio_heat import PortfolioHeatModule
from capital_management.modules.position_sizing import PositionSizingModule
from capital_management.modules.stop_risk import StopRiskModule
from capital_management.pipeline.capital_management_pipeline import CapitalManagementPipeline


class CustomVolatilityGovernor(BaseRiskModule):
    """
    Custom replacement module for testing module pluggability.
    """

    @property
    def name(self) -> str:
        return "volatility_governor"

    def _execute(self, state: CapitalManagementState) -> CapitalManagementState:
        state.volatility_multiplier = 0.90
        state.governed_risk_budget *= 0.90
        state.add_trace(self.name, "Custom Volatility Governor applied fixed 0.90 multiplier")
        state.module_results[self.name] = ModuleResult(
            module_name=self.name,
            enabled=True,
            input_summary={},
            output_summary={"volatility_multiplier": 0.90},
            status="PASS",
            reason="Custom multiplier applied",
        )
        return state


class TestCapitalManagementPipeline(unittest.TestCase):

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

    def test_full_default_pipeline_execution(self):
        pipeline = CapitalManagementPipeline()
        result = pipeline.run(account=self.account, portfolio=[], trade=self.trade)

        self.assertTrue(result.approved)
        self.assertEqual(result.symbol, "AAPL")
        self.assertEqual(result.base_risk_budget, 500.0)
        self.assertTrue(result.final_position_size > 0)
        self.assertTrue(len(result.calculation_trace) > 0)
        self.assertIn("base_risk", result.module_results)
        self.assertIn("final_validation", result.module_results)

    def test_custom_module_subset_pipeline(self):
        """
        Verify pipeline can run a reduced subset of modules without changing the modules.
        """
        custom_modules = [
            BaseRiskBudgetModule(),
            PortfolioHeatModule(),
            StopRiskModule(),
            PositionSizingModule(),
        ]
        pipeline = CapitalManagementPipeline(modules=custom_modules)
        result = pipeline.run(account=self.account, portfolio=[], trade=self.trade)

        self.assertEqual(len(result.module_results), 4)
        self.assertEqual(result.base_risk_budget, 500.0)
        self.assertEqual(result.final_position_size, 100.0)  # 500 / 5.0 = 100 shares

    def test_replaceable_module_in_pipeline(self):
        """
        Verify replacing VolatilityGovernor with CustomVolatilityGovernor seamlessly works.
        """
        pipeline = CapitalManagementPipeline()
        pipeline.modules = [
            m if m.name != "volatility_governor" else CustomVolatilityGovernor()
            for m in pipeline.modules
        ]

        result = pipeline.run(account=self.account, portfolio=[], trade=self.trade)
        self.assertTrue(result.approved)
        self.assertEqual(result.module_results["volatility_governor"].output_summary["volatility_multiplier"], 0.90)


if __name__ == "__main__":
    unittest.main()
