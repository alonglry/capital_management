"""
Comprehensive test runner for Capital Management module.
Executes 65+ test combinations across equity, forex, mixed assets,
single trades, portfolios, and diverse edge cases.
Outputs results into test_results_success.json (file A) and test_results_error.json (file B).
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capital_management.models import (
    AccountState,
    CapitalManagementConfig,
    ConvictionRiskConfig,
    DrawdownRule,
    InstrumentSpec,
    MarketData,
    Position,
    TradeCandidate,
    VolatilityRule,
)
from capital_management.pipeline import CapitalManagementPipeline


def run_all_tests():
    pipeline = CapitalManagementPipeline()

    success_records: List[Dict[str, Any]] = []
    error_records: List[Dict[str, Any]] = []

    test_cases: List[Dict[str, Any]] = []

    # =========================================================================
    # 1. EQUITY - Single & Portfolio Tests (18 test cases)
    # =========================================================================

    # Test 1: Standard Equity Long, single trade, standard account
    test_cases.append({
        "id": "EQ_01",
        "category": "equity_single",
        "description": "Standard Equity Long AAPL, clean account, baseline risk 1%",
        "account": AccountState(equity=100000.0, cash=80000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=140.0,
            slope_long=2.0,
            threshold_long=1.0,
            strategy_id="momentum",
        ),
        "instrument": InstrumentSpec(
            symbol="AAPL",
            asset_class="EQUITY",
            contract_size=1.0,
            price_increment=0.01,
            pip_size=1.0,
            quantity_increment=1.0,
            min_quantity=1.0,
            max_quantity=10000.0,
            point_value=1.0,
            base_currency="USD",
            quote_currency="USD",
            settlement_currency="USD",
            valuation_method="contract_point_value",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(atr={"AAPL": 3.5}, reference_atr={"AAPL": 3.0}),
    })

    # Test 2: Standard Equity Short MSFT
    test_cases.append({
        "id": "EQ_02",
        "category": "equity_single",
        "description": "Standard Equity Short MSFT, clean account, high conviction",
        "account": AccountState(equity=250000.0, cash=200000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="MSFT",
            asset_class="equity",
            side="short",
            entry_price=400.0,
            proposed_stop_price=420.0,
            slope_short=3.0,
            threshold_short=1.0,
            strategy_id="breakout",
        ),
        "instrument": InstrumentSpec(
            symbol="MSFT",
            asset_class="EQUITY",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.015),
        "market_data": MarketData(),
    })

    # Test 3: Equity Portfolio Existing Positions - Same sector Technology
    test_cases.append({
        "id": "EQ_03",
        "category": "equity_portfolio",
        "description": "Equity Long NVDA with existing AAPL and MSFT tech positions (sector cap test)",
        "account": AccountState(equity=500000.0, cash=300000.0, currency="USD"),
        "portfolio": [
            Position(
                symbol="AAPL",
                asset_class="equity",
                side="long",
                quantity=500,
                entry_price=150.0,
                current_price=160.0,
                stop_price=145.0,
                monetary_risk_at_stop=7500.0,
                strategy_id="momentum",
                sector="Technology",
            ),
            Position(
                symbol="MSFT",
                asset_class="equity",
                side="long",
                quantity=300,
                entry_price=380.0,
                current_price=400.0,
                stop_price=370.0,
                monetary_risk_at_stop=9000.0,
                strategy_id="breakout",
                sector="Technology",
            ),
        ],
        "trade": TradeCandidate(
            symbol="NVDA",
            asset_class="equity",
            side="long",
            entry_price=120.0,
            proposed_stop_price=110.0,
            sector="Technology",
            strategy_id="momentum",
        ),
        "instrument": InstrumentSpec(
            symbol="NVDA",
            asset_class="EQUITY",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            max_portfolio_heat_pct=0.05,
            factor_limits={"Technology": 0.25},
        ),
        "market_data": MarketData(),
    })

    # Test 4: Equity with Drawdown Multiplier Triggered
    test_cases.append({
        "id": "EQ_04",
        "category": "equity_single",
        "description": "Equity GOOG in 12% Drawdown from peak (should reduce risk budget by 50%)",
        "account": AccountState(equity=88000.0, cash=70000.0, peak_equity=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="GOOG",
            asset_class="equity",
            side="long",
            entry_price=175.0,
            proposed_stop_price=168.0,
            strategy_id="mean_reversion",
        ),
        "instrument": InstrumentSpec(symbol="GOOG", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 5: Equity in Deep Drawdown (>20%) - Expected Rejection / 0 budget
    test_cases.append({
        "id": "EQ_05",
        "category": "equity_single",
        "description": "Equity AMZN in 25% Drawdown (exceeds 20% max DD rule -> 0 multiplier)",
        "account": AccountState(equity=75000.0, cash=60000.0, peak_equity=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="AMZN",
            asset_class="equity",
            side="long",
            entry_price=180.0,
            proposed_stop_price=170.0,
        ),
        "instrument": InstrumentSpec(symbol="AMZN", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 6: Equity High Volatility Governor Scaling Down
    test_cases.append({
        "id": "EQ_06",
        "category": "equity_single",
        "description": "Equity TSLA with ATR Ratio = 2.0 (High volatility regime -> 0.50 multiplier)",
        "account": AccountState(equity=200000.0, cash=150000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="TSLA",
            asset_class="equity",
            side="long",
            entry_price=220.0,
            proposed_stop_price=200.0,
            atr_ratio=2.0,
        ),
        "instrument": InstrumentSpec(symbol="TSLA", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(atr={"TSLA": 12.0}, reference_atr={"TSLA": 6.0}),
    })

    # Test 7: Equity Low Volatility Governor (Calm market regime)
    test_cases.append({
        "id": "EQ_07",
        "category": "equity_single",
        "description": "Equity JNJ with ATR Ratio = 0.50 (Compressed volatility -> 0.75 multiplier)",
        "account": AccountState(equity=100000.0, cash=90000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="JNJ",
            asset_class="equity",
            side="long",
            entry_price=160.0,
            proposed_stop_price=155.0,
            atr_ratio=0.5,
        ),
        "instrument": InstrumentSpec(symbol="JNJ", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(atr={"JNJ": 1.0}, reference_atr={"JNJ": 2.0}),
    })

    # Test 8: Equity Portfolio Heat Capacity Exhausted (Full Heat Limit reached)
    test_cases.append({
        "id": "EQ_08",
        "category": "equity_portfolio",
        "description": "Equity portfolio existing heat already 5% of equity (equal to max heat)",
        "account": AccountState(equity=100000.0, cash=50000.0, currency="USD"),
        "portfolio": [
            Position(
                symbol="SPY",
                asset_class="equity",
                side="long",
                quantity=500,
                entry_price=500.0,
                current_price=510.0,
                stop_price=490.0,
                monetary_risk_at_stop=5000.0,  # Exactly 5% heat
                strategy_id="core",
            ),
        ],
        "trade": TradeCandidate(
            symbol="QQQ",
            asset_class="equity",
            side="long",
            entry_price=450.0,
            proposed_stop_price=440.0,
        ),
        "instrument": InstrumentSpec(symbol="QQQ", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.05),
        "market_data": MarketData(),
    })

    # Test 9: Equity with Transaction Costs (Spread + Commission + Slippage)
    test_cases.append({
        "id": "EQ_09",
        "category": "equity_single",
        "description": "Equity with explicit transaction costs in trade candidate",
        "account": AccountState(equity=100000.0, cash=80000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="META",
            asset_class="equity",
            side="long",
            entry_price=500.0,
            proposed_stop_price=480.0,
            commission=5.0,
            spread=0.10,
            expected_slippage=0.05,
        ),
        "instrument": InstrumentSpec(symbol="META", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            transaction_cost_assumptions={
                "default_commission": 2.0,
                "default_spread": 0.05,
                "default_slippage": 0.02,
                "commission_type": "per_unit",
                "commission_rate_basis": 0.001,
            },
        ),
        "market_data": MarketData(),
    })

    # Test 10: Equity Stop Missing -> Resolved from ATR (1.5 x ATR default)
    test_cases.append({
        "id": "EQ_10",
        "category": "equity_single",
        "description": "Equity Trade Candidate missing proposed_stop_price, auto-resolved via ATR",
        "account": AccountState(equity=100000.0, cash=80000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="NFLX",
            asset_class="equity",
            side="long",
            entry_price=600.0,
            proposed_stop_price=None,
            atr=15.0,
        ),
        "instrument": InstrumentSpec(symbol="NFLX", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(atr={"NFLX": 15.0}),
    })

    # Test 11: Equity High Correlation with existing position
    test_cases.append({
        "id": "EQ_11",
        "category": "equity_portfolio",
        "description": "Equity AMD with existing NVDA position and 0.90 correlation matrix",
        "account": AccountState(equity=200000.0, cash=150000.0, currency="USD"),
        "portfolio": [
            Position(
                symbol="NVDA",
                asset_class="equity",
                side="long",
                quantity=100,
                entry_price=120.0,
                current_price=125.0,
                stop_price=115.0,
                monetary_risk_at_stop=1000.0,
                strategy_id="momentum",
            )
        ],
        "trade": TradeCandidate(
            symbol="AMD",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=140.0,
        ),
        "instrument": InstrumentSpec(symbol="AMD", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            max_correlation_adjusted_risk_pct=0.02,
        ),
        "market_data": MarketData(
            correlation_matrix={"AMD": {"NVDA": 0.90}, "NVDA": {"AMD": 0.90}}
        ),
    })

    # Test 12: Equity Stress Test Mode 'reduce'
    test_cases.append({
        "id": "EQ_12",
        "category": "equity_single",
        "description": "Equity CRM with stress test policy 'reduce' under gap risk scenario",
        "account": AccountState(equity=100000.0, cash=80000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="CRM",
            asset_class="equity",
            side="long",
            entry_price=250.0,
            proposed_stop_price=240.0,
        ),
        "instrument": InstrumentSpec(symbol="CRM", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            stress_policy="reduce",
            stress_limits={"max_stress_risk_pct": 0.015, "gap_pct": 0.02, "extra_slippage_pct": 0.005},
        ),
        "market_data": MarketData(),
    })

    # Test 13: Equity Fractional Quantity Disallowed (Integer Rounding)
    test_cases.append({
        "id": "EQ_13",
        "category": "equity_single",
        "description": "Equity integer share rounding verification (quantity_increment=1.0)",
        "account": AccountState(equity=33333.33, cash=33333.33, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="IBM",
            asset_class="equity",
            side="long",
            entry_price=190.0,
            proposed_stop_price=183.33,
        ),
        "instrument": InstrumentSpec(
            symbol="IBM",
            asset_class="EQUITY",
            quantity_increment=1.0,
            min_quantity=1.0,
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 14: Equity Min Quantity Boundary (Position too small for 1 share)
    test_cases.append({
        "id": "EQ_14",
        "category": "equity_single",
        "description": "Equity BRK.A high share price where 1% risk of small account cannot afford 1 share",
        "account": AccountState(equity=5000.0, cash=5000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="BRK.A",
            asset_class="equity",
            side="long",
            entry_price=600000.0,
            proposed_stop_price=580000.0,
        ),
        "instrument": InstrumentSpec(
            symbol="BRK.A",
            asset_class="EQUITY",
            min_quantity=1.0,
            quantity_increment=1.0,
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 15: Equity Portfolio with Multiple Diverse Strategies
    test_cases.append({
        "id": "EQ_15",
        "category": "equity_portfolio",
        "description": "Equity Portfolio with momentum, breakout, mean_reversion strategies running concurrently",
        "account": AccountState(equity=300000.0, cash=200000.0, currency="USD"),
        "portfolio": [
            Position(
                symbol="DIS",
                asset_class="equity",
                side="long",
                quantity=200,
                entry_price=100.0,
                current_price=105.0,
                stop_price=95.0,
                monetary_risk_at_stop=1000.0,
                strategy_id="momentum",
            ),
            Position(
                symbol="WMT",
                asset_class="equity",
                side="short",
                quantity=150,
                entry_price=70.0,
                current_price=68.0,
                stop_price=74.0,
                monetary_risk_at_stop=900.0,
                strategy_id="breakout",
            ),
        ],
        "trade": TradeCandidate(
            symbol="COST",
            asset_class="equity",
            side="long",
            entry_price=800.0,
            proposed_stop_price=780.0,
            strategy_id="mean_reversion",
        ),
        "instrument": InstrumentSpec(symbol="COST", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            strategy_allocations={"mean_reversion": 1.0, "momentum": 0.8, "breakout": 0.8},
        ),
        "market_data": MarketData(),
    })

    # Test 16: Equity Single with Power Conviction Mapping
    test_cases.append({
        "id": "EQ_16",
        "category": "equity_single",
        "description": "Equity BA with power gamma conviction mapping (gamma=2.0)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="BA",
            asset_class="equity",
            side="long",
            entry_price=180.0,
            proposed_stop_price=170.0,
            slope_long=1.5,
            threshold_long=1.0,
        ),
        "instrument": InstrumentSpec(symbol="BA", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            conviction_risk=ConvictionRiskConfig(mapping_type="power", power_gamma=2.0),
        ),
        "market_data": MarketData(),
    })

    # Test 17: Equity Portfolio Existing Short Positions
    test_cases.append({
        "id": "EQ_17",
        "category": "equity_portfolio",
        "description": "Equity portfolio with existing short positions proposing a new short position",
        "account": AccountState(equity=150000.0, cash=120000.0, currency="USD"),
        "portfolio": [
            Position(symbol="INTC", asset_class="equity", side="short", quantity=400, entry_price=30.0, current_price=28.0, stop_price=32.0, monetary_risk_at_stop=800.0, strategy_id="short_strat"),
        ],
        "trade": TradeCandidate(
            symbol="AMD",
            asset_class="equity",
            side="short",
            entry_price=150.0,
            proposed_stop_price=160.0,
            strategy_id="short_strat",
        ),
        "instrument": InstrumentSpec(symbol="AMD", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 18: Equity Single with Max Trade Risk Bound
    test_cases.append({
        "id": "EQ_18",
        "category": "equity_single",
        "description": "Equity trade capped by max_trade_risk_pct = 0.0075 even when conviction requests 0.015",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="HD",
            asset_class="equity",
            side="long",
            entry_price=350.0,
            proposed_stop_price=335.0,
            slope_long=5.0,
            threshold_long=1.0,
        ),
        "instrument": InstrumentSpec(symbol="HD", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            max_trade_risk_pct=0.0075,
            conviction_risk=ConvictionRiskConfig(max_multiplier=2.0),
        ),
        "market_data": MarketData(),
    })

    # =========================================================================
    # 2. FOREX - Single & Portfolio Tests (18 test cases)
    # =========================================================================

    # Test 19: Standard Forex EURUSD Long (Direct Quote)
    test_cases.append({
        "id": "FX_01",
        "category": "forex_single",
        "description": "Forex EURUSD Long, standard 10 USD/pip pip_value_per_lot",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0810,  # 40 pips
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
            spread=0.0001,
            commission=3.50,
            strategy_id="fx_trend",
        ),
        "instrument": InstrumentSpec.create_default("EURUSD", "forex"),
        "instrument_patch": {"metadata_verified": True, "metadata_source": "test_runner"},
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 20: Forex USDJPY Long (JPY Quote Currency, Indirect FX Rate conversion)
    test_cases.append({
        "id": "FX_02",
        "category": "forex_single",
        "description": "Forex USDJPY Long, JPY quote currency requiring USDJPY conversion rate for pip value",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="USDJPY",
            asset_class="forex",
            side="long",
            entry_price=155.50,
            proposed_stop_price=154.50,  # 100 pips (1.00 yen)
            pip_value_per_lot=6.43,      # approx 1000/155.5
            pip_value_currency="USD",
            strategy_id="fx_carry",
        ),
        "instrument": InstrumentSpec(
            symbol="USDJPY",
            asset_class="FOREX",
            base_currency="USD",
            quote_currency="JPY",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.01,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=100.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(fx_rates={"USDJPY": 155.50}),
    })

    # Test 21: Forex GBPUSD Short (40 pips stop)
    test_cases.append({
        "id": "FX_03",
        "category": "forex_single",
        "description": "Forex GBPUSD Short, 40 pips stop loss",
        "account": AccountState(equity=75000.0, cash=75000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="GBPUSD",
            asset_class="forex",
            side="short",
            entry_price=1.2700,
            proposed_stop_price=1.2740,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
            strategy_id="momentum",
        ),
        "instrument": InstrumentSpec(
            symbol="GBPUSD",
            asset_class="FOREX",
            base_currency="GBP",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=100.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 22: Forex Cross Pair EURGBP with GBP Account Currency
    test_cases.append({
        "id": "FX_04",
        "category": "forex_single",
        "description": "Forex EURGBP Cross with GBP Account Currency (Quote = Account)",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="GBP"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURGBP",
            asset_class="forex",
            side="long",
            entry_price=0.8550,
            proposed_stop_price=0.8520,  # 30 pips
            pip_value_per_lot=10.0,      # 10 GBP per lot
            pip_value_currency="GBP",
            strategy_id="mean_reversion",
        ),
        "instrument": InstrumentSpec(
            symbol="EURGBP",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="GBP",
            settlement_currency="GBP",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=100.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 23: Forex Portfolio with Multiple FX Pairs (USD Exposure Aggregation)
    test_cases.append({
        "id": "FX_05",
        "category": "forex_portfolio",
        "description": "Forex portfolio with EURUSD and GBPUSD open positions, adding AUDUSD (USD exposure check)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [
            Position(
                symbol="EURUSD",
                asset_class="forex",
                side="long",
                quantity=1.5,
                entry_price=1.0800,
                current_price=1.0850,
                stop_price=1.0760,
                monetary_risk_at_stop=600.0,
                strategy_id="fx_trend",
                currency_exposure={"USD": -1.0, "EUR": 1.0},
            ),
            Position(
                symbol="GBPUSD",
                asset_class="forex",
                side="long",
                quantity=1.0,
                entry_price=1.2650,
                current_price=1.2700,
                stop_price=1.2610,
                monetary_risk_at_stop=400.0,
                strategy_id="fx_trend",
                currency_exposure={"USD": -1.0, "GBP": 1.0},
            ),
        ],
        "trade": TradeCandidate(
            symbol="AUDUSD",
            asset_class="forex",
            side="long",
            entry_price=0.6600,
            proposed_stop_price=0.6560,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
            currency_exposure={"USD": -1.0, "AUD": 1.0},
            strategy_id="fx_trend",
        ),
        "instrument": InstrumentSpec(
            symbol="AUDUSD",
            asset_class="FOREX",
            base_currency="AUD",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            max_portfolio_heat_pct=0.04,
            factor_limits={"USD": 2.5, "AUD": 1.5},
        ),
        "market_data": MarketData(),
    })

    # Test 24: Forex Stop Resolution from ATR (pip calculation)
    test_cases.append({
        "id": "FX_06",
        "category": "forex_single",
        "description": "Forex USDCHF with no proposed stop, resolving stop from ATR (0.0040 = 40 pips)",
        "account": AccountState(equity=60000.0, cash=60000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="USDCHF",
            asset_class="forex",
            side="short",
            entry_price=0.9000,
            proposed_stop_price=None,
            pip_value_per_lot=11.11,
            pip_value_currency="USD",
            atr=0.0040,
        ),
        "instrument": InstrumentSpec(
            symbol="USDCHF",
            asset_class="FOREX",
            base_currency="USD",
            quote_currency="CHF",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(atr={"USDCHF": 0.0040}),
    })

    # Test 25: Forex Microlot Sizing Floor (quantity increment 0.01)
    test_cases.append({
        "id": "FX_07",
        "category": "forex_single",
        "description": "Forex microlot floor calculation (e.g. 0.375 lots rounded down to 0.37 lots)",
        "account": AccountState(equity=15000.0, cash=15000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0810,  # 40 pips = $400/lot risk
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 26: Forex Max Lots Cap Enforcement
    test_cases.append({
        "id": "FX_08",
        "category": "forex_single",
        "description": "Forex large institutional account hitting InstrumentSpec max_quantity limit (10.0 lots)",
        "account": AccountState(equity=5000000.0, cash=5000000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0840,  # 10 pips = $100/lot -> theoretical 500 lots
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=10.0,  # Strict broker cap
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 27: Forex Correlated Risk Reduction between EURUSD and GBPUSD
    test_cases.append({
        "id": "FX_09",
        "category": "forex_portfolio",
        "description": "Forex EURUSD with existing GBPUSD long and correlation 0.85",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [
            Position(
                symbol="GBPUSD",
                asset_class="forex",
                side="long",
                quantity=2.0,
                entry_price=1.2700,
                current_price=1.2750,
                stop_price=1.2650,
                monetary_risk_at_stop=1000.0,
                strategy_id="fx_trend",
            )
        ],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0800,  # 50 pips
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            max_correlation_adjusted_risk_pct=0.02,
        ),
        "market_data": MarketData(
            correlation_matrix={"EURUSD": {"GBPUSD": 0.85}, "GBPUSD": {"EURUSD": 0.85}}
        ),
    })

    # Test 28: Forex Conviction Scaling (High Conviction Long)
    test_cases.append({
        "id": "FX_10",
        "category": "forex_single",
        "description": "Forex NZDUSD with strong positive slope/conviction multiplier = 1.5x",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="NZDUSD",
            asset_class="forex",
            side="long",
            entry_price=0.6000,
            proposed_stop_price=0.5960,  # 40 pips
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
            slope_long=5.0,
            threshold_long=1.0,
            strategy_id="momentum",
        ),
        "instrument": InstrumentSpec(
            symbol="NZDUSD",
            asset_class="FOREX",
            base_currency="NZD",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            max_trade_risk_pct=0.02,
            conviction_risk=ConvictionRiskConfig(min_multiplier=0.5, max_multiplier=1.5),
        ),
        "market_data": MarketData(),
    })

    # Test 29: Forex Conviction Penalty on Conflicting Signals
    test_cases.append({
        "id": "FX_11",
        "category": "forex_single",
        "description": "Forex USDCAD with conflicting long and short signals triggering conflict penalty",
        "account": AccountState(equity=80000.0, cash=80000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="USDCAD",
            asset_class="forex",
            side="long",
            entry_price=1.3600,
            proposed_stop_price=1.3550,
            pip_value_per_lot=7.35,
            pip_value_currency="USD",
            slope_long=2.0,
            threshold_long=1.0,
            slope_short=1.8,
            threshold_short=1.0,
        ),
        "instrument": InstrumentSpec(
            symbol="USDCAD",
            asset_class="FOREX",
            base_currency="USD",
            quote_currency="CAD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            conviction_risk=ConvictionRiskConfig(conflict_penalty=0.5),
        ),
        "market_data": MarketData(),
    })

    # Test 30: Forex Stress Testing with Spread Widening
    test_cases.append({
        "id": "FX_12",
        "category": "forex_single",
        "description": "Forex EURJPY with stress testing (5 pips gap and slippage in risk calculation)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURJPY",
            asset_class="forex",
            side="short",
            entry_price=168.00,
            proposed_stop_price=169.00,
            pip_value_per_lot=6.43,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURJPY",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="JPY",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.01,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            stress_policy="reduce",
            stress_limits={"max_stress_risk_pct": 0.012, "gap_pct": 0.005, "extra_slippage_pct": 0.002},
        ),
        "market_data": MarketData(),
    })

    # Test 31: Forex with High Transaction Commission and Spread
    test_cases.append({
        "id": "FX_13",
        "category": "forex_single",
        "description": "Forex trade with high fixed lot commission ($7/lot) and 3 pip spread",
        "account": AccountState(equity=20000.0, cash=20000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0820,  # 30 pips = $300/lot
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
            commission=7.0,
            spread=0.0003,
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 32: Forex Multiple Open Positions Total Portfolio Heat Test
    test_cases.append({
        "id": "FX_14",
        "category": "forex_portfolio",
        "description": "Forex portfolio with 4 open currency positions approaching heat ceiling",
        "account": AccountState(equity=200000.0, cash=180000.0, currency="USD"),
        "portfolio": [
            Position(symbol="EURUSD", asset_class="forex", side="long", quantity=2.0, entry_price=1.08, current_price=1.085, stop_price=1.075, monetary_risk_at_stop=1000.0, strategy_id="fx1"),
            Position(symbol="GBPUSD", asset_class="forex", side="long", quantity=2.0, entry_price=1.26, current_price=1.268, stop_price=1.255, monetary_risk_at_stop=1000.0, strategy_id="fx1"),
            Position(symbol="AUDUSD", asset_class="forex", side="short", quantity=2.0, entry_price=0.67, current_price=0.665, stop_price=0.675, monetary_risk_at_stop=1000.0, strategy_id="fx2"),
            Position(symbol="USDJPY", asset_class="forex", side="long", quantity=2.0, entry_price=154.0, current_price=155.0, stop_price=153.5, monetary_risk_at_stop=1000.0, strategy_id="fx2"),
        ],
        "trade": TradeCandidate(
            symbol="USDCAD",
            asset_class="forex",
            side="long",
            entry_price=1.3600,
            proposed_stop_price=1.3550,
            pip_value_per_lot=7.35,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="USDCAD",
            asset_class="FOREX",
            base_currency="USD",
            quote_currency="CAD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.03),  # 3% max = $6000, current = $4000
        "market_data": MarketData(),
    })

    # Test 33: Forex Strategy Weighting Allocation Check
    test_cases.append({
        "id": "FX_15",
        "category": "forex_single",
        "description": "Forex carry strategy with strategy allocation multiplier = 0.50",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="USDMXN",
            asset_class="forex",
            side="short",
            entry_price=17.50,
            proposed_stop_price=17.80,
            pip_value_per_lot=5.71,
            pip_value_currency="USD",
            strategy_id="carry",
        ),
        "instrument": InstrumentSpec(
            symbol="USDMXN",
            asset_class="FOREX",
            base_currency="USD",
            quote_currency="MXN",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            strategy_allocations={"carry": 0.50, "default": 1.0},
        ),
        "market_data": MarketData(),
    })

    # Test 34: Forex Cross Pair AUDNZD with Direct FX Conversion via market rates
    test_cases.append({
        "id": "FX_16",
        "category": "forex_single",
        "description": "Forex AUDNZD cross with market data NZDUSD FX rate for conversion",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="AUDNZD",
            asset_class="forex",
            side="long",
            entry_price=1.1000,
            proposed_stop_price=1.0950,
            pip_value_per_lot=10.0,
            pip_value_currency="NZD",
        ),
        "instrument": InstrumentSpec(
            symbol="AUDNZD",
            asset_class="FOREX",
            base_currency="AUD",
            quote_currency="NZD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(fx_rates={"NZDUSD": 0.60}),
    })

    # Test 35: Forex Tight Stop Distance (5 pips)
    test_cases.append({
        "id": "FX_17",
        "category": "forex_single",
        "description": "Forex EURUSD Scalping with 5 pips tight stop loss",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0845,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=100.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 36: Forex Wide Swing Stop Distance (200 pips)
    test_cases.append({
        "id": "FX_18",
        "category": "forex_single",
        "description": "Forex GBPJPY Swing trade with 200 pips wide stop loss",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="GBPJPY",
            asset_class="forex",
            side="long",
            entry_price=195.00,
            proposed_stop_price=193.00,
            pip_value_per_lot=6.45,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="GBPJPY",
            asset_class="FOREX",
            base_currency="GBP",
            quote_currency="JPY",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.01,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # =========================================================================
    # 3. MIX OF BOTH (EQUITY + FOREX) - Single & Portfolio Tests (12 test cases)
    # =========================================================================

    # Test 37: Mixed Portfolio: Holding Equities (AAPL, TSLA), proposing Forex EURUSD
    test_cases.append({
        "id": "MIX_01",
        "category": "mix_portfolio",
        "description": "Mixed Portfolio: Holding Equity positions AAPL & TSLA, proposing Forex EURUSD trade",
        "account": AccountState(equity=250000.0, cash=180000.0, currency="USD"),
        "portfolio": [
            Position(symbol="AAPL", asset_class="equity", side="long", quantity=300, entry_price=150.0, current_price=160.0, stop_price=145.0, monetary_risk_at_stop=1500.0, strategy_id="equity_trend"),
            Position(symbol="TSLA", asset_class="equity", side="long", quantity=100, entry_price=200.0, current_price=220.0, stop_price=190.0, monetary_risk_at_stop=1000.0, strategy_id="equity_trend"),
        ],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0800,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
            strategy_id="fx_trend",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.05),
        "market_data": MarketData(),
    })

    # Test 38: Mixed Portfolio: Holding Forex positions (EURUSD, USDJPY), proposing Equity MSFT
    test_cases.append({
        "id": "MIX_02",
        "category": "mix_portfolio",
        "description": "Mixed Portfolio: Holding Forex EURUSD & USDJPY, proposing Equity MSFT",
        "account": AccountState(equity=300000.0, cash=250000.0, currency="USD"),
        "portfolio": [
            Position(symbol="EURUSD", asset_class="forex", side="long", quantity=2.0, entry_price=1.08, current_price=1.085, stop_price=1.075, monetary_risk_at_stop=1000.0, strategy_id="fx1"),
            Position(symbol="USDJPY", asset_class="forex", side="long", quantity=2.0, entry_price=150.0, current_price=152.0, stop_price=149.0, monetary_risk_at_stop=1300.0, strategy_id="fx2"),
        ],
        "trade": TradeCandidate(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            entry_price=410.0,
            proposed_stop_price=395.0,
            strategy_id="equity_breakout",
        ),
        "instrument": InstrumentSpec(symbol="MSFT", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.05),
        "market_data": MarketData(),
    })

    # Test 39: Mixed Portfolio: Multi-asset cross correlation (SPY equity vs EURUSD forex)
    test_cases.append({
        "id": "MIX_03",
        "category": "mix_portfolio",
        "description": "Mixed Portfolio: Risk correlation between SPY equity and EURUSD forex (risk-on asset co-movement)",
        "account": AccountState(equity=200000.0, cash=150000.0, currency="USD"),
        "portfolio": [
            Position(symbol="SPY", asset_class="equity", side="long", quantity=200, entry_price=500.0, current_price=510.0, stop_price=495.0, monetary_risk_at_stop=1000.0, strategy_id="macro_core"),
        ],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0900,
            proposed_stop_price=1.0850,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_correlation_adjusted_risk_pct=0.02),
        "market_data": MarketData(
            correlation_matrix={"EURUSD": {"SPY": 0.70}, "SPY": {"EURUSD": 0.70}}
        ),
    })

    # Test 40: Mixed Portfolio: Drawdown Governor acting across combined multi-asset account
    test_cases.append({
        "id": "MIX_04",
        "category": "mix_portfolio",
        "description": "Mixed Multi-Asset Account in 8% Drawdown (testing equity sizing under multi-asset portfolio)",
        "account": AccountState(equity=184000.0, cash=120000.0, peak_equity=200000.0, currency="USD"),  # 8% DD -> 0.75 multiplier
        "portfolio": [
            Position(symbol="GBPUSD", asset_class="forex", side="short", quantity=1.0, entry_price=1.28, current_price=1.29, stop_price=1.30, monetary_risk_at_stop=1000.0, strategy_id="macro"),
        ],
        "trade": TradeCandidate(
            symbol="NVDA",
            asset_class="equity",
            side="long",
            entry_price=130.0,
            proposed_stop_price=120.0,
        ),
        "instrument": InstrumentSpec(symbol="NVDA", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Test 41: Mixed Portfolio: Factor limit test (USD Factor shared across Equity and FX)
    test_cases.append({
        "id": "MIX_05",
        "category": "mix_portfolio",
        "description": "Factor limit test: USD factor exposure aggregated across US equities and USD FX pairs",
        "account": AccountState(equity=200000.0, cash=150000.0, currency="USD"),
        "portfolio": [
            Position(symbol="AAPL", asset_class="equity", side="long", quantity=200, entry_price=150.0, current_price=155.0, stop_price=145.0, monetary_risk_at_stop=1000.0, strategy_id="eq", currency_exposure={"USD": 1.0}),
            Position(symbol="EURUSD", asset_class="forex", side="short", quantity=1.0, entry_price=1.08, current_price=1.075, stop_price=1.09, monetary_risk_at_stop=1000.0, strategy_id="fx", currency_exposure={"USD": 1.0, "EUR": -1.0}),
        ],
        "trade": TradeCandidate(
            symbol="USDJPY",
            asset_class="forex",
            side="long",
            entry_price=155.0,
            proposed_stop_price=154.0,
            pip_value_per_lot=6.45,
            pip_value_currency="USD",
            currency_exposure={"USD": 1.0, "JPY": -1.0},
        ),
        "instrument": InstrumentSpec(
            symbol="USDJPY",
            asset_class="FOREX",
            base_currency="USD",
            quote_currency="JPY",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.01,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01, factor_limits={"USD": 2.0}),
        "market_data": MarketData(),
    })

    # Test 42: Mixed Portfolio: High Portfolio Heat constraint binding on multi-asset addition
    test_cases.append({
        "id": "MIX_06",
        "category": "mix_portfolio",
        "description": "Multi-asset portfolio heat constraint limiting new FX trade capacity",
        "account": AccountState(equity=100000.0, cash=60000.0, currency="USD"),
        "portfolio": [
            Position(symbol="AAPL", asset_class="equity", side="long", quantity=100, entry_price=150.0, current_price=150.0, stop_price=140.0, monetary_risk_at_stop=1000.0, strategy_id="s1"),
            Position(symbol="MSFT", asset_class="equity", side="long", quantity=50, entry_price=400.0, current_price=400.0, stop_price=380.0, monetary_risk_at_stop=1000.0, strategy_id="s1"),
            Position(symbol="EURUSD", asset_class="forex", side="long", quantity=1.0, entry_price=1.08, current_price=1.08, stop_price=1.07, monetary_risk_at_stop=1000.0, strategy_id="s2"),
        ],
        "trade": TradeCandidate(
            symbol="GBPUSD",
            asset_class="forex",
            side="long",
            entry_price=1.2700,
            proposed_stop_price=1.2650,  # 50 pips = $500/lot
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="GBPUSD",
            asset_class="FOREX",
            base_currency="GBP",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.015, max_portfolio_heat_pct=0.035),  # max heat $3500, existing $3000 -> capacity only $500
        "market_data": MarketData(),
    })

    # Test 43: Mixed Portfolio: Global Stress Test Policy 'reject'
    test_cases.append({
        "id": "MIX_07",
        "category": "mix_portfolio",
        "description": "Multi-asset stress test with 'reject' policy when stress loss exceeds capacity",
        "account": AccountState(equity=100000.0, cash=80000.0, currency="USD"),
        "portfolio": [
            Position(symbol="TSLA", asset_class="equity", side="long", quantity=100, entry_price=200.0, current_price=200.0, stop_price=190.0, monetary_risk_at_stop=1000.0, strategy_id="s1"),
        ],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0800,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            stress_policy="reject",
            stress_limits={"max_stress_risk_pct": 0.005, "gap_pct": 0.02, "extra_slippage_pct": 0.01},
        ),
        "market_data": MarketData(),
    })

    # Test 44: Mixed Portfolio: Cross-asset Volatility Governors
    test_cases.append({
        "id": "MIX_08",
        "category": "mix_portfolio",
        "description": "Mixed portfolio with elevated volatility regime on equity target",
        "account": AccountState(equity=150000.0, cash=120000.0, currency="USD"),
        "portfolio": [
            Position(symbol="EURUSD", asset_class="forex", side="long", quantity=1.0, entry_price=1.08, current_price=1.085, stop_price=1.075, monetary_risk_at_stop=500.0, strategy_id="fx"),
        ],
        "trade": TradeCandidate(
            symbol="AMD",
            asset_class="equity",
            side="long",
            entry_price=150.0,
            proposed_stop_price=140.0,
            atr_ratio=1.6,  # elevated volatility -> 0.75
        ),
        "instrument": InstrumentSpec(symbol="AMD", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(atr={"AMD": 8.0}, reference_atr={"AMD": 5.0}),
    })

    # Test 45: Mixed Portfolio: Strategy Allocation with cross-asset strategies
    test_cases.append({
        "id": "MIX_09",
        "category": "mix_portfolio",
        "description": "Cross-asset strategy allocation: momentum at 0.75x vs carry at 0.50x",
        "account": AccountState(equity=200000.0, cash=160000.0, currency="USD"),
        "portfolio": [
            Position(symbol="NVDA", asset_class="equity", side="long", quantity=100, entry_price=120.0, current_price=125.0, stop_price=115.0, monetary_risk_at_stop=500.0, strategy_id="momentum"),
        ],
        "trade": TradeCandidate(
            symbol="AUDJPY",
            asset_class="forex",
            side="long",
            entry_price=100.0,
            proposed_stop_price=99.0,
            pip_value_per_lot=6.45,
            pip_value_currency="USD",
            strategy_id="carry",
        ),
        "instrument": InstrumentSpec(
            symbol="AUDJPY",
            asset_class="FOREX",
            base_currency="AUD",
            quote_currency="JPY",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.01,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(
            base_risk_pct=0.01,
            strategy_allocations={"momentum": 0.75, "carry": 0.50},
        ),
        "market_data": MarketData(),
    })

    # Test 46: Mixed Portfolio: Full multi-asset reconciliation and ledger verification
    test_cases.append({
        "id": "MIX_10",
        "category": "mix_portfolio",
        "description": "Full risk ledger reconciliation across multi-asset portfolio",
        "account": AccountState(equity=500000.0, cash=400000.0, currency="USD"),
        "portfolio": [
            Position(symbol="SPY", asset_class="equity", side="long", quantity=200, entry_price=500.0, current_price=505.0, stop_price=490.0, monetary_risk_at_stop=2000.0, strategy_id="macro"),
            Position(symbol="EURUSD", asset_class="forex", side="short", quantity=2.0, entry_price=1.09, current_price=1.085, stop_price=1.10, monetary_risk_at_stop=2000.0, strategy_id="fx"),
        ],
        "trade": TradeCandidate(
            symbol="QQQ",
            asset_class="equity",
            side="long",
            entry_price=450.0,
            proposed_stop_price=440.0,
            strategy_id="tech_momentum",
        ),
        "instrument": InstrumentSpec(symbol="QQQ", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.06),
        "market_data": MarketData(),
    })

    # Test 47: Mixed Portfolio: Multi-currency account with non-USD Base Currency (EUR)
    test_cases.append({
        "id": "MIX_11",
        "category": "mix_portfolio",
        "description": "EUR-denominated account holding US Equity and trading EURUSD",
        "account": AccountState(equity=200000.0, cash=150000.0, currency="EUR"),
        "portfolio": [
            Position(symbol="AAPL", asset_class="equity", side="long", quantity=100, entry_price=150.0, current_price=150.0, stop_price=140.0, monetary_risk_at_stop=1000.0, strategy_id="eq"),
        ],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0800,
            pip_value_per_lot=10.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="EUR",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(fx_rates={"EURUSD": 1.0850}),
    })

    # Test 48: Mixed Portfolio: High Equity & Forex Heat with Near Rejection Sizing
    test_cases.append({
        "id": "MIX_12",
        "category": "mix_portfolio",
        "description": "Mixed portfolio with remaining heat capacity allowing only partial allocation",
        "account": AccountState(equity=100000.0, cash=80000.0, currency="USD"),
        "portfolio": [
            Position(symbol="AAPL", asset_class="equity", side="long", quantity=100, entry_price=150.0, current_price=150.0, stop_price=140.0, monetary_risk_at_stop=1000.0, strategy_id="eq"),
            Position(symbol="EURUSD", asset_class="forex", side="long", quantity=2.0, entry_price=1.08, current_price=1.08, stop_price=1.07, monetary_risk_at_stop=2000.0, strategy_id="fx"),
            Position(symbol="GBPUSD", asset_class="forex", side="long", quantity=1.5, entry_price=1.27, current_price=1.27, stop_price=1.26, monetary_risk_at_stop=1500.0, strategy_id="fx"),
        ],
        "trade": TradeCandidate(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            entry_price=400.0,
            proposed_stop_price=390.0,  # $10 stop -> 1 share = $10 risk
        ),
        "instrument": InstrumentSpec(symbol="MSFT", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.05),  # max $5000, current $4500 -> remaining capacity $500
        "market_data": MarketData(),
    })

    # =========================================================================
    # 4. EDGE CASES & STRESS COMBINATIONS (26 test cases)
    # =========================================================================

    # Edge 1: 0 Initial Account Equity
    test_cases.append({
        "id": "EDGE_01",
        "category": "edge_account",
        "description": "Account equity = 0.0 (Zero initial equity edge case)",
        "account": AccountState(equity=0.0, cash=0.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 2: Negative Account Equity
    test_cases.append({
        "id": "EDGE_02",
        "category": "edge_account",
        "description": "Negative account equity = -5000.0 (Deficit account)",
        "account": AccountState(equity=-5000.0, cash=-5000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 3: 0 Cash with Positive Equity (Illiquid portfolio)
    test_cases.append({
        "id": "EDGE_03",
        "category": "edge_account",
        "description": "Account equity = 100,000 but Free Cash = 0.0",
        "account": AccountState(equity=100000.0, cash=0.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 4: Negative Cash Balance (Margin call / overdraft)
    test_cases.append({
        "id": "EDGE_04",
        "category": "edge_account",
        "description": "Account equity = 50,000 but Free Cash = -10,000 (Margin debit)",
        "account": AccountState(equity=50000.0, cash=-10000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 5: Unverified Instrument Metadata (metadata_verified = False)
    test_cases.append({
        "id": "EDGE_05",
        "category": "edge_instrument",
        "description": "InstrumentSpec with metadata_verified = False (Must trigger hard rejection in production)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=False, metadata_source="unverified_feed"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 6: Missing InstrumentSpec entirely (None passed)
    test_cases.append({
        "id": "EDGE_06",
        "category": "edge_instrument",
        "description": "InstrumentSpec is None passed to pipeline (Missing required metadata rejection)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": None,
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 7: Invalid Stop Loss Direction - LONG with Stop > Entry Price
    test_cases.append({
        "id": "EDGE_07",
        "category": "edge_trade",
        "description": "Invalid Stop Direction: LONG trade with Stop (160) > Entry (150)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=160.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 8: Invalid Stop Loss Direction - SHORT with Stop < Entry Price
    test_cases.append({
        "id": "EDGE_08",
        "category": "edge_trade",
        "description": "Invalid Stop Direction: SHORT trade with Stop (140) < Entry (150)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="short", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 9: Stop Price exactly equal to Entry Price (Zero Stop Distance)
    test_cases.append({
        "id": "EDGE_09",
        "category": "edge_trade",
        "description": "Stop Price exactly equal to Entry Price (150.0 == 150.0)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=150.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 10: 0 Entry Price
    test_cases.append({
        "id": "EDGE_10",
        "category": "edge_trade",
        "description": "Trade entry price = 0.0",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=0.0, proposed_stop_price=-10.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 11: Negative Entry Price
    test_cases.append({
        "id": "EDGE_11",
        "category": "edge_trade",
        "description": "Trade entry price = -50.0",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=-50.0, proposed_stop_price=-60.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 12: Missing Pip Value on Forex Trade Candidate
    test_cases.append({
        "id": "EDGE_12",
        "category": "edge_trade",
        "description": "Forex trade candidate with pip_value_per_lot = None and pip_value_currency = None",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0800,
            pip_value_per_lot=None,
            pip_value_currency=None,
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 13: 0 Pip Value on Forex Trade Candidate
    test_cases.append({
        "id": "EDGE_13",
        "category": "edge_trade",
        "description": "Forex trade candidate with pip_value_per_lot = 0.0",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            entry_price=1.0850,
            proposed_stop_price=1.0800,
            pip_value_per_lot=0.0,
            pip_value_currency="USD",
        ),
        "instrument": InstrumentSpec(
            symbol="EURUSD",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="USD",
            settlement_currency="USD",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 14: Base Risk Pct = 0.0
    test_cases.append({
        "id": "EDGE_14",
        "category": "edge_config",
        "description": "CapitalManagementConfig with base_risk_pct = 0.0 (Zero base risk budget)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.0),
        "market_data": MarketData(),
    })

    # Edge 15: Base Risk Pct Negative
    test_cases.append({
        "id": "EDGE_15",
        "category": "edge_config",
        "description": "CapitalManagementConfig with negative base_risk_pct = -0.01 (Raises ValueError on init)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config_factory": lambda: CapitalManagementConfig(base_risk_pct=-0.01),
        "market_data": MarketData(),
    })

    # Edge 16: Base Risk Pct > 100%
    test_cases.append({
        "id": "EDGE_16",
        "category": "edge_config",
        "description": "CapitalManagementConfig with excessive base_risk_pct = 1.5 (150% risk, raises ValueError on init)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config_factory": lambda: CapitalManagementConfig(base_risk_pct=1.5),
        "market_data": MarketData(),
    })

    # Edge 17: Extreme Conviction Multiplier Bounds (Inverted min > max)
    test_cases.append({
        "id": "EDGE_17",
        "category": "edge_config",
        "description": "Conviction config inverted min > max (min=2.0, max=0.5 -> ValueError on init)",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config_factory": lambda: CapitalManagementConfig(
            conviction_risk=ConvictionRiskConfig(min_multiplier=2.0, max_multiplier=0.5)
        ),
        "market_data": MarketData(),
    })

    # Edge 18: Non-existent FX Cross Rate Conversion without fallback
    test_cases.append({
        "id": "EDGE_18",
        "category": "edge_instrument",
        "description": "Exotic Forex pair EURTRY with TRY pip value currency and no EURTRY or TRYUSD market rate",
        "account": AccountState(equity=50000.0, cash=50000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(
            symbol="EURTRY",
            asset_class="forex",
            side="long",
            entry_price=35.0,
            proposed_stop_price=34.0,
            pip_value_per_lot=300.0,
            pip_value_currency="TRY",
        ),
        "instrument": InstrumentSpec(
            symbol="EURTRY",
            asset_class="FOREX",
            base_currency="EUR",
            quote_currency="TRY",
            settlement_currency="TRY",
            contract_size=100000.0,
            pip_size=0.0001,
            quantity_increment=0.01,
            min_quantity=0.01,
            max_quantity=50.0,
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(fx_rates={}),  # No FX rate provided for TRY->USD
    })

    # Edge 19: Trade Candidate with NaN entry price
    test_cases.append({
        "id": "EDGE_19",
        "category": "edge_trade",
        "description": "Trade Candidate with float('nan') entry price",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=float("nan"), proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 20: Trade Candidate with Infinity stop price
    test_cases.append({
        "id": "EDGE_20",
        "category": "edge_trade",
        "description": "Trade Candidate with float('inf') proposed stop price",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=float("inf")),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 21: Mismatched asset_class (Trade says equity, Instrument says FOREX)
    test_cases.append({
        "id": "EDGE_21",
        "category": "edge_mismatch",
        "description": "Mismatched asset_class: TradeCandidate asset_class='equity' vs InstrumentSpec asset_class='FOREX'",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(
            symbol="AAPL",
            asset_class="FOREX",
            base_currency="AAP",
            quote_currency="USD",
            settlement_currency="USD",
            valuation_method="pip_value_per_lot",
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 22: Unknown side (neither 'long' nor 'short')
    test_cases.append({
        "id": "EDGE_22",
        "category": "edge_trade",
        "description": "Invalid trade side 'buy_hold'",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="buy_hold", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 23: InstrumentSpec min_quantity > max_quantity
    test_cases.append({
        "id": "EDGE_23",
        "category": "edge_instrument",
        "description": "InstrumentSpec invalid bounds: min_quantity=1000 > max_quantity=100",
        "account": AccountState(equity=100000.0, cash=100000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(
            symbol="AAPL",
            asset_class="EQUITY",
            min_quantity=1000.0,
            max_quantity=100.0,
            metadata_verified=True,
            metadata_source="test_runner",
        ),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 24: Extremely huge equity (Billionaire account stress)
    test_cases.append({
        "id": "EDGE_24",
        "category": "edge_account",
        "description": "Ultra-large institutional equity = $10,000,000,000 (10B USD)",
        "account": AccountState(equity=10_000_000_000.0, cash=8_000_000_000.0, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 25: Microscopic equity ($0.05 account)
    test_cases.append({
        "id": "EDGE_25",
        "category": "edge_account",
        "description": "Microscopic account equity = $0.05",
        "account": AccountState(equity=0.05, cash=0.05, currency="USD"),
        "portfolio": [],
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01),
        "market_data": MarketData(),
    })

    # Edge 26: Massive Portfolio with 50 existing positions
    huge_portfolio = [
        Position(
            symbol=f"STOCK_{i}",
            asset_class="equity",
            side="long",
            quantity=10,
            entry_price=100.0,
            current_price=100.0,
            stop_price=90.0,
            monetary_risk_at_stop=100.0,
            strategy_id=f"strat_{i % 5}",
            sector=f"Sector_{i % 10}",
        )
        for i in range(50)
    ]
    test_cases.append({
        "id": "EDGE_26",
        "category": "edge_portfolio",
        "description": "Massive portfolio with 50 existing positions ($5,000 aggregated heat)",
        "account": AccountState(equity=200000.0, cash=100000.0, currency="USD"),
        "portfolio": huge_portfolio,
        "trade": TradeCandidate(symbol="AAPL", asset_class="equity", side="long", entry_price=150.0, proposed_stop_price=140.0),
        "instrument": InstrumentSpec(symbol="AAPL", asset_class="EQUITY", metadata_verified=True, metadata_source="test_runner"),
        "config": CapitalManagementConfig(base_risk_pct=0.01, max_portfolio_heat_pct=0.05),
        "market_data": MarketData(),
    })

    print(f"Total test cases to execute: {len(test_cases)}")

    # Execute all test cases
    for tc in test_cases:
        tc_id = tc["id"]
        category = tc["category"]
        desc = tc["description"]

        # Build condition record summary
        condition_record = {
            "test_id": tc_id,
            "category": category,
            "description": desc,
            "account": {
                "equity": tc["account"].equity if "account" in tc and tc["account"] else None,
                "cash": tc["account"].cash if "account" in tc and tc["account"] else None,
                "currency": tc["account"].currency if "account" in tc and tc["account"] else None,
                "peak_equity": tc["account"].peak_equity if "account" in tc and tc["account"] else None,
            } if "account" in tc and tc["account"] else None,
            "portfolio_count": len(tc["portfolio"]) if "portfolio" in tc else 0,
            "trade": {
                "symbol": tc["trade"].symbol if "trade" in tc and tc["trade"] else None,
                "asset_class": tc["trade"].asset_class if "trade" in tc and tc["trade"] else None,
                "side": tc["trade"].side if "trade" in tc and tc["trade"] else None,
                "entry_price": str(tc["trade"].entry_price) if "trade" in tc and tc["trade"] else None,
                "proposed_stop_price": str(tc["trade"].proposed_stop_price) if "trade" in tc and tc["trade"] else None,
                "strategy_id": tc["trade"].strategy_id if "trade" in tc and tc["trade"] else None,
                "pip_value_per_lot": tc["trade"].pip_value_per_lot if "trade" in tc and tc["trade"] else None,
            } if "trade" in tc and tc["trade"] else None,
            "instrument": {
                "symbol": tc["instrument"].symbol if tc.get("instrument") else None,
                "asset_class": tc["instrument"].asset_class if tc.get("instrument") else None,
                "valuation_method": tc["instrument"].valuation_method if tc.get("instrument") else None,
                "metadata_verified": tc["instrument"].metadata_verified if tc.get("instrument") else None,
                "metadata_source": tc["instrument"].metadata_source if tc.get("instrument") else None,
            } if tc.get("instrument") else None,
        }

        try:
            # Handle config factory if present
            if "config_factory" in tc:
                config = tc["config_factory"]()
            else:
                config = tc.get("config")

            instrument = tc.get("instrument")
            if instrument and "instrument_patch" in tc:
                for k, v in tc["instrument_patch"].items():
                    setattr(instrument, k, v)

            result = pipeline.run(
                account=tc["account"],
                portfolio=tc["portfolio"],
                trade=tc["trade"],
                market_data=tc.get("market_data", MarketData()),
                config=config,
                instrument=instrument,
            )

            # Success execution (pipeline ran without unhandled Python exception)
            outcome_data = {
                "approved": result.approved,
                "symbol": result.symbol,
                "side": result.side,
                "asset_class": result.asset_class,
                "base_risk_budget": result.base_risk_budget,
                "requested_risk_budget": result.requested_risk_budget,
                "governed_risk_budget": result.governed_risk_budget,
                "permitted_risk_budget": result.permitted_risk_budget,
                "raw_position_size": result.raw_position_size,
                "executable_position_size": result.executable_position_size,
                "actual_stop_loss_risk": result.actual_stop_loss_risk,
                "actual_total_risk": result.actual_total_risk,
                "rejection_reasons": result.rejection_reasons,
                "warnings": result.warnings,
                "binding_constraints": result.binding_constraints,
            }

            success_records.append({
                "test_id": tc_id,
                "category": category,
                "description": desc,
                "conditions": condition_record,
                "outcome": outcome_data,
                "status": "COMPLETED_WITHOUT_EXCEPTION",
            })

        except Exception as e:
            # Error execution (raised an unhandled Python exception)
            error_type = type(e).__name__
            error_msg = str(e)
            tb = traceback.format_exc()

            error_records.append({
                "test_id": tc_id,
                "category": category,
                "description": desc,
                "conditions": condition_record,
                "error_type": error_type,
                "error_message": error_msg,
                "traceback": tb,
                "status": "FAILED_WITH_EXCEPTION",
            })

    # Save File A: Tests without error (completed execution)
    file_a_path = Path(__file__).resolve().parent / "test_results_success.json"
    with open(file_a_path, "w", encoding="utf-8") as f:
        json.dump(success_records, f, indent=2)

    # Save File B: Tests with error (raised exception)
    file_b_path = Path(__file__).resolve().parent / "test_results_error.json"
    with open(file_b_path, "w", encoding="utf-8") as f:
        json.dump(error_records, f, indent=2)

    print(f"\n=======================================================")
    print(f"Test Run Completed!")
    print(f"Total Tests Executed: {len(test_cases)}")
    print(f"File A (Completed without exception): {len(success_records)} records -> {file_a_path}")
    print(f"File B (Failed with exception):        {len(error_records)} records -> {file_b_path}")
    print(f"=======================================================\n")


if __name__ == "__main__":
    run_all_tests()
