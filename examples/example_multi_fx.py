"""
Worked Example — Multi-Pair Forex Portfolio Risk Management.
"""

from capital_management.models import (
    AccountState,
    CapitalManagementConfig,
    InstrumentSpec,
    MarketData,
    Position,
    TradeCandidate,
)
from capital_management.pipeline import CapitalManagementPipeline


def main():
    account = AccountState(equity=100000.0, cash=100000.0, currency="USD")

    existing_positions = [
        Position(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            quantity=1.0,
            entry_price=1.0800,
            current_price=1.0850,
            stop_price=1.0760,
            monetary_risk_at_stop=400.0,
            strategy_id="fx_trend",
        ),
        Position(
            symbol="GBPUSD",
            asset_class="forex",
            side="long",
            quantity=0.5,
            entry_price=1.2600,
            current_price=1.2650,
            stop_price=1.2540,
            monetary_risk_at_stop=300.0,
            strategy_id="fx_trend",
        ),
    ]

    candidate_trade = TradeCandidate(
        symbol="AUDUSD",
        asset_class="forex",
        side="long",
        entry_price=0.6500,
        proposed_stop_price=0.6460,
        pip_value_per_lot=10.0,
        pip_value_currency="USD",
        slope_long=2.5,
        threshold_long=1.0,
        slope_short=0.0,
        threshold_short=1.0,
        strategy_id="fx_trend",
        atr=0.0040,
    )

    inst = InstrumentSpec(
        symbol="AUDUSD",
        asset_class="FOREX",
        contract_size=100000.0,
        pip_size=0.0001,
        quantity_increment=0.01,
        min_quantity=0.01,
        quote_currency="USD",
        base_currency="AUD",
        settlement_currency="USD",
        metadata_verified=True,
        metadata_source="explicit_example",
    )

    correlation_data = {
        "EURUSD": {"EURUSD": 1.0, "GBPUSD": 0.80, "AUDUSD": 0.75},
        "GBPUSD": {"EURUSD": 0.80, "GBPUSD": 1.0, "AUDUSD": 0.70},
        "AUDUSD": {"EURUSD": 0.75, "GBPUSD": 0.70, "AUDUSD": 1.0},
    }

    market_data = MarketData(
        correlation_matrix=correlation_data,
        atr={"AUDUSD": 0.0040},
        reference_atr={"AUDUSD": 0.0040},
    )
    config = CapitalManagementConfig(
        base_risk_pct=0.01,
        max_portfolio_heat_pct=0.03,
        max_correlation_adjusted_risk_pct=0.025,
        stress_policy="reduce",
        factor_limits={"USD": 5.0, "EUR": 3.0, "GBP": 3.0, "AUD": 3.0},
    )

    pipeline = CapitalManagementPipeline()
    result = pipeline.run(
        account=account,
        portfolio=existing_positions,
        trade=candidate_trade,
        market_data=market_data,
        config=config,
        instrument=inst,
    )

    print("=== MULTI-FOREX PORTFOLIO RISK REPORT ===")
    print(f"Candidate Symbol: {result.symbol} | Side: {result.side.upper()}")
    print(f"Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
    print(f"Current Portfolio Heat: {result.current_portfolio_heat:.2%}")
    print(f"Projected Portfolio Heat: {result.projected_portfolio_heat:.2%}")
    print(f"Heat Capacity: ${result.portfolio_heat_capacity:,.2f}")
    print(f"Correlation Capacity: ${result.correlation_risk_capacity:,.2f}")
    print(f"Permitted Risk Budget: ${result.permitted_risk_budget:,.2f}")
    print(f"Executable Floor Lots: {result.executable_position_size:.4f}")
    print(f"Actual Total Risk: ${result.actual_total_risk:,.2f}")
    print(f"Actual Total Risk <= Permitted: {result.actual_total_risk <= result.permitted_risk_budget}")


if __name__ == "__main__":
    main()
