"""
Tests for TradeCandidate optional proposed_stop_price and canonical stop resolution mechanism.
"""

import math
import pytest

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.trade_candidate import TradeCandidate, resolve_effective_stop_price
from capital_management.pipeline.capital_management_pipeline import CapitalManagementPipeline


def test_1_strategy_stop_supplied():
    """
    TEST 1 — Strategy stop supplied takes precedence over ATR.
    """
    candidate = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=100.0,
        proposed_stop_price=95.0,
        atr=10.0,
    )
    config = CapitalManagementConfig(default_stop_method="atr", default_stop_atr_multiplier=1.5)

    effective_stop, source, dist = resolve_effective_stop_price(candidate, config=config)
    assert effective_stop == 95.0
    assert source == "strategy"
    assert dist == 5.0


def test_2_long_default_atr_stop():
    """
    TEST 2 — LONG default ATR stop calculation.
    """
    candidate = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=100.0,
        proposed_stop_price=None,
        atr=10.0,
    )
    config = CapitalManagementConfig(default_stop_method="atr", default_stop_atr_multiplier=1.5)

    effective_stop, source, dist = resolve_effective_stop_price(candidate, config=config)
    assert dist == 15.0
    assert effective_stop == 85.0
    assert source == "atr"


def test_3_short_default_atr_stop():
    """
    TEST 3 — SHORT default ATR stop calculation.
    """
    candidate = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="short",
        entry_price=100.0,
        proposed_stop_price=None,
        atr=10.0,
    )
    config = CapitalManagementConfig(default_stop_method="atr", default_stop_atr_multiplier=1.5)

    effective_stop, source, dist = resolve_effective_stop_price(candidate, config=config)
    assert dist == 15.0
    assert effective_stop == 115.0
    assert source == "atr"


def test_4_invalid_atr():
    """
    TEST 4 — Invalid ATR values (0, -1, NaN, inf) must cause resolution rejection.
    """
    config = CapitalManagementConfig(default_stop_method="atr", default_stop_atr_multiplier=1.5)

    for invalid_atr in [0.0, -1.0, float("nan"), float("inf"), float("-inf")]:
        candidate = TradeCandidate(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            entry_price=100.0,
            proposed_stop_price=None,
            atr=invalid_atr,
        )
        with pytest.raises(ValueError):
            resolve_effective_stop_price(candidate, config=config)


def test_5_invalid_multiplier():
    """
    TEST 5 — Invalid default_stop_atr_multiplier values must cause rejection.
    """
    candidate = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=100.0,
        proposed_stop_price=None,
        atr=10.0,
    )

    for invalid_mult in [0.0, -1.0, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            CapitalManagementConfig(default_stop_method="atr", default_stop_atr_multiplier=invalid_mult)


def test_6_invalid_strategy_stop_direction():
    """
    TEST 6 — Invalid strategy stop direction (LONG stop > entry or SHORT stop < entry) must reject.
    """
    config = CapitalManagementConfig()

    # LONG with stop > entry
    cand_long = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=100.0,
        proposed_stop_price=105.0,
    )
    with pytest.raises(ValueError):
        resolve_effective_stop_price(cand_long, config=config)

    # SHORT with stop < entry
    cand_short = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="short",
        entry_price=100.0,
        proposed_stop_price=95.0,
    )
    with pytest.raises(ValueError):
        resolve_effective_stop_price(cand_short, config=config)


def test_7_zero_distance_stop():
    """
    TEST 7 — Zero-distance stop (proposed_stop == entry_price) must reject.
    """
    config = CapitalManagementConfig()
    candidate = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=100.0,
        proposed_stop_price=100.0,
    )
    with pytest.raises(ValueError):
        resolve_effective_stop_price(candidate, config=config)


def test_8_no_strategy_stop_and_no_default_stop_method():
    """
    TEST 8 — No strategy stop and default_stop_method == 'none' must reject.
    """
    config = CapitalManagementConfig(default_stop_method="none")
    candidate = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=100.0,
        proposed_stop_price=None,
        atr=10.0,
    )
    with pytest.raises(ValueError):
        resolve_effective_stop_price(candidate, config=config)


def test_9_sizing_uses_resolved_stop():
    """
    TEST 9 — Verify that proposed_stop_price = None produces identical position sizing result
    to explicitly supplying the corresponding ATR-derived stop.
    """
    account = AccountState(equity=100000.0, cash=100000.0, currency="USD")
    instrument = InstrumentSpec(
        symbol="AAPL",
        asset_class="equity",
        quote_currency="USD",
        metadata_verified=True,
        metadata_source="test",
    )
    config = CapitalManagementConfig(base_risk_pct=0.01, default_stop_method="atr", default_stop_atr_multiplier=1.5)

    atr_val = 2.0
    mult_val = 1.5
    entry_val = 100.0
    calc_stop_val = entry_val - (atr_val * mult_val)  # 97.0

    # Candidate A: proposed_stop_price = None
    candidate_a = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=entry_val,
        proposed_stop_price=None,
        atr=atr_val,
    )

    # Candidate B: proposed_stop_price = 97.0 explicitly
    candidate_b = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=entry_val,
        proposed_stop_price=calc_stop_val,
        atr=atr_val,
    )

    pipeline = CapitalManagementPipeline()
    result_a = pipeline.run(account=account, portfolio=[], trade=candidate_a, config=config, instrument=instrument)
    result_b = pipeline.run(account=account, portfolio=[], trade=candidate_b, config=config, instrument=instrument)

    assert result_a.approved is True
    assert result_b.approved is True

    assert math.isclose(result_a.stop_price, result_b.stop_price, rel_tol=1e-9)
    assert math.isclose(result_a.final_position_size, result_b.final_position_size, rel_tol=1e-9)
    assert result_a.stop_price_source == "atr"
    assert result_b.stop_price_source == "strategy"
