"""
Unit tests for ConvictionRiskAllocatorModule.
"""

import unittest

import numpy as np
import pandas as pd

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig, ConvictionRiskConfig
from capital_management.models.market_data import MarketData
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.conviction_allocator import ConvictionRiskAllocatorModule
from capital_management.modules.conviction_mapping import PowerConvictionMapping


class TestConvictionRiskAllocatorModule(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=75000.0)
        self.config = CapitalManagementConfig(base_risk_pct=0.005)
        self.module = ConvictionRiskAllocatorModule()

    def _create_state(
        self,
        slope_l: float | pd.Series,
        thresh_l: float | pd.Series,
        slope_s: float | pd.Series,
        thresh_s: float | pd.Series,
        config: CapitalManagementConfig = None,
        base_budget: float = 500.0,
    ) -> CapitalManagementState:
        if config is None:
            config = self.config
        trade = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=145.0,
            strategy_id="trend",
            slope_long=slope_l,
            threshold_long=thresh_l,
            slope_short=slope_s,
            threshold_short=thresh_s,
        )
        return CapitalManagementState(
            account=self.account,
            portfolio=[],
            trade=trade,
            market_data=MarketData(),
            config=config,
            base_risk_budget=base_budget,
            adjusted_risk_budget=base_budget,
        )

    def test_1_long_conviction_only(self):
        """
        Long slope 1.30, threshold 1.00 (max=1.50) -> raw = (1.3-1.0)/0.5 = 0.60.
        Short slope 0.20, threshold 1.00 -> raw = -1.60 -> clipped = 0.
        Net = 0.60, conflict = 0.
        conviction_mult = 0.50 + (1.50-0.50)*0.60 = 1.10.
        Requested risk = 500 * 1.10 = $550.
        """
        state = self._create_state(1.30, 1.00, 0.20, 1.00)
        updated = self.module.process(state)

        self.assertAlmostEqual(updated.long_conviction, 0.60, places=4)
        self.assertAlmostEqual(updated.short_conviction, 0.0, places=4)
        self.assertAlmostEqual(updated.net_conviction, 0.60, places=4)
        self.assertAlmostEqual(updated.directional_strength, 0.60, places=4)
        self.assertAlmostEqual(updated.signal_conflict, 0.0, places=4)
        self.assertAlmostEqual(updated.conviction_multiplier, 1.10, places=4)
        self.assertAlmostEqual(updated.conflict_multiplier, 1.00, places=4)
        self.assertAlmostEqual(updated.requested_risk_budget, 550.0, places=2)

    def test_2_short_conviction_only(self):
        state = self._create_state(0.20, 1.00, 1.30, 1.00)
        updated = self.module.process(state)

        self.assertAlmostEqual(updated.long_conviction, 0.0, places=4)
        self.assertAlmostEqual(updated.short_conviction, 0.60, places=4)
        self.assertAlmostEqual(updated.net_conviction, -0.60, places=4)
        self.assertAlmostEqual(updated.directional_strength, 0.60, places=4)
        self.assertAlmostEqual(updated.conviction_multiplier, 1.10, places=4)
        self.assertAlmostEqual(updated.requested_risk_budget, 550.0, places=2)

    def test_3_both_weak(self):
        state = self._create_state(1.10, 1.00, 1.10, 1.00)
        updated = self.module.process(state)

        self.assertAlmostEqual(updated.long_conviction, 0.20, places=4)
        self.assertAlmostEqual(updated.short_conviction, 0.20, places=4)
        self.assertAlmostEqual(updated.net_conviction, 0.0, places=4)
        self.assertAlmostEqual(updated.directional_strength, 0.0, places=4)
        self.assertAlmostEqual(updated.signal_conflict, 0.20, places=4)

    def test_4_both_strong(self):
        state = self._create_state(1.50, 1.00, 1.50, 1.00)
        updated = self.module.process(state)

        self.assertAlmostEqual(updated.long_conviction, 1.00, places=4)
        self.assertAlmostEqual(updated.short_conviction, 1.00, places=4)
        self.assertAlmostEqual(updated.net_conviction, 0.0, places=4)
        self.assertAlmostEqual(updated.signal_conflict, 1.00, places=4)
        # conflict_mult = 1 - 0.5 * 1.0 = 0.50
        self.assertAlmostEqual(updated.conflict_multiplier, 0.50, places=4)
        # conv_mult at dir_str=0 is 0.50
        # requested = 500 * 0.50 * 0.50 = 125.0
        self.assertAlmostEqual(updated.requested_risk_budget, 125.0, places=2)

    def test_5_long_short_conflict(self):
        state = self._create_state(1.40, 1.00, 1.20, 1.00)
        updated = self.module.process(state)

        self.assertAlmostEqual(updated.long_conviction, 0.80, places=4)
        self.assertAlmostEqual(updated.short_conviction, 0.40, places=4)
        self.assertAlmostEqual(updated.signal_conflict, 0.40, places=4)
        # conflict_mult = 1 - 0.5 * 0.40 = 0.80
        self.assertAlmostEqual(updated.conflict_multiplier, 0.80, places=4)

    def test_6_threshold_zero(self):
        state = self._create_state(1.0, 0.0, 1.0, 0.0)
        updated = self.module.process(state)
        self.assertEqual(updated.long_conviction, 0.0)
        self.assertEqual(updated.short_conviction, 0.0)

    def test_7_negative_slope(self):
        state = self._create_state(-0.5, 1.0, -0.2, 1.0)
        updated = self.module.process(state)
        self.assertEqual(updated.long_conviction, 0.0)
        self.assertEqual(updated.short_conviction, 0.0)

    def test_8_very_large_slope(self):
        state = self._create_state(100.0, 1.0, 0.0, 1.0)
        updated = self.module.process(state)
        self.assertEqual(updated.long_conviction, 1.0)

    def test_9_conviction_clipping(self):
        state = self._create_state(2.50, 1.00, -5.00, 1.00)
        updated = self.module.process(state)
        self.assertEqual(updated.long_conviction, 1.00)
        self.assertEqual(updated.short_conviction, 0.00)

    def test_10_minimum_conviction_multiplier(self):
        state = self._create_state(1.00, 1.00, 1.00, 1.00)  # net = 0
        updated = self.module.process(state)
        self.assertEqual(updated.conviction_multiplier, 0.50)

    def test_11_maximum_conviction_multiplier(self):
        state = self._create_state(1.50, 1.00, 0.00, 1.00)  # dir_strength = 1.0
        updated = self.module.process(state)
        self.assertEqual(updated.conviction_multiplier, 1.50)

    def test_12_conflict_penalty(self):
        cfg = CapitalManagementConfig(
            conviction_risk=ConvictionRiskConfig(conflict_penalty=0.80)
        )
        state = self._create_state(1.40, 1.00, 1.20, 1.00, config=cfg)
        updated = self.module.process(state)
        # min(0.8, 0.4) = 0.4. conflict_mult = 1 - 0.8 * 0.4 = 0.68
        self.assertAlmostEqual(updated.conflict_multiplier, 0.68, places=4)

    def test_13_disabled_module(self):
        cfg = CapitalManagementConfig()
        cfg.modules["conviction_allocator"] = False
        state = self._create_state(1.30, 1.00, 0.20, 1.00, config=cfg)
        updated = self.module.process(state)
        self.assertEqual(updated.adjusted_risk_budget, 500.0)
        self.assertEqual(updated.module_results["conviction_allocator"].status, "SKIPPED")

    def test_14_scalar_input(self):
        state = self._create_state(1.30, 1.00, 0.20, 1.00)
        updated = self.module.process(state)
        self.assertTrue(isinstance(updated.requested_risk_budget, float))
        self.assertEqual(updated.requested_risk_budget, 550.0)

    def test_15_vectorized_input(self):
        s_long = pd.Series([1.30, 1.50, 1.00])
        t_long = pd.Series([1.00, 1.00, 1.00])
        s_short = pd.Series([0.20, 0.00, 1.00])
        t_short = pd.Series([1.00, 1.00, 1.00])

        state = self._create_state(s_long, t_long, s_short, t_short)
        updated = self.module.process(state)

        self.assertTrue(isinstance(updated.requested_risk_budget, pd.Series))
        self.assertEqual(len(updated.requested_risk_budget), 3)

        # Verify element 0 matches scalar result 550.0
        self.assertAlmostEqual(updated.requested_risk_budget.iloc[0], 550.0, places=2)

    def test_16_power_mapping(self):
        module = ConvictionRiskAllocatorModule(mapping=PowerConvictionMapping(gamma=2.0))
        state = self._create_state(1.30, 1.00, 0.20, 1.00)
        updated = module.process(state)

        # dir_strength = 0.60 -> mapped = 0.60^2 = 0.36
        # conv_mult = 0.50 + 1.00 * 0.36 = 0.86
        # requested = 500 * 0.86 = 430.0
        self.assertAlmostEqual(updated.conviction_multiplier, 0.86, places=4)
        self.assertAlmostEqual(updated.requested_risk_budget, 430.0, places=2)


if __name__ == "__main__":
    unittest.main()
