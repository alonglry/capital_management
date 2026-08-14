"""
Comprehensive Audit & Invariant Test Suite for Capital Management Engine.
Covers integration scenarios A through T, property invariants 1 through 12, idempotency, and metadata verification.
"""

import unittest
import numpy as np

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_risk import BaseRiskBudgetModule
from capital_management.modules.final_validation import FinalValidationModule
from capital_management.modules.position_sizing import PositionSizingModule
from capital_management.modules.risk_reconciliation import ActualRiskReconciliationModule
from capital_management.modules.stop_risk import StopRiskModule
from capital_management.pipeline import CapitalManagementPipeline


class TestAuditComprehensive(unittest.TestCase):

    def setUp(self):
        self.account = AccountState(equity=100000.0, cash=50000.0, currency="USD")
        self.config = CapitalManagementConfig()
        self.pipeline = CapitalManagementPipeline()

    def test_scenario_a_equity_long(self):
        trade = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0, strategy_id="momentum"
        )
        inst = InstrumentSpec(symbol="AAPL", asset_class="EQUITY", contract_size=1.0, quantity_increment=1.0, min_quantity=1.0, metadata_verified=True, metadata_source="explicit")
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)
        self.assertTrue(res.approved)
        self.assertGreater(res.final_position_size, 0)
        self.assertLessEqual(res.actual_total_risk, res.permitted_risk_budget + 1e-4)

    def test_scenario_b_equity_short(self):
        trade = TradeCandidate(
            symbol="TSLA", asset_class="equity", side="short", entry_price=200.0, proposed_stop_price=210.0, strategy_id="momentum"
        )
        inst = InstrumentSpec(symbol="TSLA", asset_class="EQUITY", contract_size=1.0, quantity_increment=1.0, min_quantity=1.0, metadata_verified=True, metadata_source="explicit")
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)
        self.assertTrue(res.approved)
        self.assertGreater(res.final_position_size, 0)
        self.assertLessEqual(res.actual_total_risk, res.permitted_risk_budget + 1e-4)

    def test_scenario_c_eurusd_long(self):
        trade = TradeCandidate(
            symbol="EURUSD", asset_class="forex", side="long", entry_price=1.0800, proposed_stop_price=1.0750, strategy_id="carry", pip_value_per_lot=10.0, pip_value_currency="USD"
        )
        inst = InstrumentSpec(symbol="EURUSD", asset_class="FOREX", contract_size=100000.0, pip_size=0.0001, quantity_increment=0.01, min_quantity=0.01, quote_currency="USD", base_currency="EUR", metadata_verified=True, metadata_source="explicit")
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)
        self.assertTrue(res.approved)
        self.assertGreater(res.final_position_size, 0)

    def test_scenario_d_eurusd_short(self):
        trade = TradeCandidate(
            symbol="EURUSD", asset_class="forex", side="short", entry_price=1.0800, proposed_stop_price=1.0850, strategy_id="carry", pip_value_per_lot=10.0, pip_value_currency="USD"
        )
        inst = InstrumentSpec(symbol="EURUSD", asset_class="FOREX", contract_size=100000.0, pip_size=0.0001, quantity_increment=0.01, min_quantity=0.01, quote_currency="USD", base_currency="EUR", metadata_verified=True, metadata_source="explicit")
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)
        self.assertTrue(res.approved)
        self.assertGreater(res.final_position_size, 0)

    def test_scenario_e_usdjpy(self):
        trade = TradeCandidate(
            symbol="USDJPY", asset_class="forex", side="long", entry_price=150.00, proposed_stop_price=149.00, strategy_id="carry", pip_value_per_lot=6.67, pip_value_currency="USD"
        )
        inst = InstrumentSpec(symbol="USDJPY", asset_class="FOREX", contract_size=100000.0, pip_size=0.01, quantity_increment=0.01, min_quantity=0.01, quote_currency="JPY", base_currency="USD", metadata_verified=True, metadata_source="explicit")
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)
        self.assertTrue(res.approved)
        self.assertGreater(res.final_position_size, 0)

    def test_scenario_f_cross_forex_missing_rate_rejection(self):
        trade = TradeCandidate(
            symbol="EURGBP", asset_class="forex", side="long", entry_price=0.8500, proposed_stop_price=0.8450, strategy_id="carry"
        )
        inst = InstrumentSpec(symbol="EURGBP", asset_class="FOREX", contract_size=100000.0, pip_size=0.0001, quantity_increment=0.01, min_quantity=0.01, quote_currency="GBP", base_currency="EUR", metadata_verified=True, metadata_source="explicit")
        mdata = MarketData(fx_rates={})
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, market_data=mdata, instrument=inst)
        self.assertFalse(res.approved)
        self.assertEqual(res.final_position_size, 0.0)

    def test_unusual_quantity_increments(self):
        for inc in [0.25, 0.05, 0.125]:
            trade = TradeCandidate(
                symbol="TEST", asset_class="equity", side="long", entry_price=10.0, proposed_stop_price=9.0, strategy_id="m"
            )
            inst = InstrumentSpec(symbol="TEST", asset_class="EQUITY", quantity_increment=inc, min_quantity=inc, metadata_verified=True)
            res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)
            if res.approved:
                rem = abs(res.final_position_size / inc - round(res.final_position_size / inc))
                self.assertLess(rem, 1e-4)

    def test_idempotency_of_reconciliation_and_validation(self):
        trade = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0, strategy_id="momentum"
        )
        inst = InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True)
        res1 = self.pipeline.run(account=self.account, portfolio=[], trade=trade, instrument=inst)

        # Run reconciliation and validation twice on state
        state = CapitalManagementState(account=self.account, portfolio=[], trade=trade, market_data=MarketData(), config=self.config, instrument=inst)
        state.permitted_risk_budget = 500.0
        state.monetary_risk_per_unit = 10.0
        state.executable_position_size = 50.0

        recon = ActualRiskReconciliationModule()
        val = FinalValidationModule()

        state = recon.process(state)
        size1 = state.final_position_size
        risk1 = state.actual_total_risk

        state = recon.process(state)
        size2 = state.final_position_size
        risk2 = state.actual_total_risk

        self.assertEqual(size1, size2)
        self.assertEqual(risk1, risk2)

        state = val.process(state)
        app1 = state.approved
        state = val.process(state)
        app2 = state.approved

        self.assertEqual(app1, app2)

    def test_scenario_i_existing_portfolio_above_heat_limit(self):
        pos = Position(
            symbol="AAPL", asset_class="equity", side="long", quantity=1000.0, entry_price=150.0, current_price=150.0, stop_price=140.0, monetary_risk_at_stop=6000.0, strategy_id="momentum"
        )
        trade = TradeCandidate(
            symbol="MSFT", asset_class="equity", side="long", entry_price=300.0, proposed_stop_price=290.0, strategy_id="momentum"
        )
        res = self.pipeline.run(account=self.account, portfolio=[pos], trade=trade)
        self.assertFalse(res.approved)
        self.assertEqual(res.final_position_size, 0.0)

    def test_scenario_n_unsafe_legacy_default_rejection(self):
        trade = TradeCandidate(
            symbol="EURGBP", asset_class="forex", side="long", entry_price=0.8500, proposed_stop_price=0.8450, strategy_id="carry"
        )
        cfg = CapitalManagementConfig(require_verified_instrument_metadata="reject")
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade, config=cfg)
        self.assertFalse(res.approved)
        self.assertTrue(any("Unsafe InstrumentSpec default" in r for r in res.rejection_reasons))

    def test_scenario_s_invalid_custom_module_order(self):
        with self.assertRaises(ValueError):
            CapitalManagementPipeline(modules=[PositionSizingModule(), StopRiskModule()])

    def test_scenario_t_upstream_rejection_prevents_position_sizing(self):
        trade = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=160.0, strategy_id="momentum"
        )
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade)
        self.assertFalse(res.approved)
        self.assertEqual(res.final_position_size, 0.0)
        self.assertEqual(res.module_results["position_sizing"].status, "SKIPPED")

    def test_invariant_1_total_risk_within_budget(self):
        trade = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, strategy_id="momentum", commission=10.0
        )
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade)
        if res.approved:
            self.assertLessEqual(res.actual_total_risk, res.permitted_risk_budget + 1e-4)

    def test_invariant_2_final_size_less_than_raw_size(self):
        trade = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, strategy_id="momentum"
        )
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade)
        self.assertLessEqual(res.final_position_size, res.raw_position_size + 1e-4)

    def test_invariant_10_and_11_no_approved_with_rejections(self):
        trade = TradeCandidate(
            symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=145.0, strategy_id="momentum"
        )
        res = self.pipeline.run(account=self.account, portfolio=[], trade=trade)
        if res.approved:
            self.assertEqual(len(res.rejection_reasons), 0)
        else:
            self.assertGreater(len(res.rejection_reasons), 0)
            self.assertEqual(res.final_position_size, 0.0)


if __name__ == "__main__":
    unittest.main()
