"""
Worked Example — Multi-Position Equity Portfolio Risk Management.
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
    account = AccountState(equity=100000.0, cash=60000.0, currency="USD")

    existing_positions = [
        Position(
            symbol="AAPL",
            asset_class="equity",
            side="long",
            quantity=100,
            entry_price=170.0,
            current_price=180.0,
            stop_price=160.0,
            monetary_risk_at_stop=2000.0,
            strategy_id="momentum",
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            quantity=50,
            entry_price=310.0,
            current_price=330.0,
            stop_price=290.0,
            monetary_risk_at_stop=1000.0,
            strategy_id="trend",
            sector="Technology",
        ),
    ]

    candidate_trade = TradeCandidate(
        symbol="NVDA",
        asset_class="equity",
        side="long",
        entry_price=450.0,
        proposed_stop_price=420.0,
        slope_long=2.0,
        threshold_long=1.0,
        slope_short=0.0,
        threshold_short=1.0,
        strategy_id="momentum",
        sector="Technology",
        atr=10.0,
    )

    inst = InstrumentSpec(
        symbol="NVDA",
        asset_class="EQUITY",
        contract_size=1.0,
        point_value=1.0,
        quantity_increment=1.0,
        min_quantity=1.0,
        quote_currency="USD",
        settlement_currency="USD",
        metadata_verified=True,
        metadata_source="explicit_example",
    )

    correlation_data = {
        "AAPL": {"AAPL": 1.0, "MSFT": 0.65, "NVDA": 0.70},
        "MSFT": {"AAPL": 0.65, "MSFT": 1.0, "NVDA": 0.60},
        "NVDA": {"AAPL": 0.70, "MSFT": 0.60, "NVDA": 1.0},
    }

    market_data = MarketData(
        correlation_matrix=correlation_data,
        atr={"NVDA": 10.0},
        reference_atr={"NVDA": 10.0},
    )
    config = CapitalManagementConfig(
        base_risk_pct=0.01,
        max_portfolio_heat_pct=0.05,
        max_correlation_adjusted_risk_pct=0.04,
        stress_policy="reduce",
        factor_limits={"Technology": 0.50},
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

    print("=== MULTI-EQUITY PORTFOLIO RISK REPORT ===")
    print(f"Candidate Symbol: {result.symbol} | Side: {result.side.upper()}")
    print(f"Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
    print(f"Current Portfolio Heat: {result.current_portfolio_heat:.2%}")
    print(f"Projected Portfolio Heat: {result.projected_portfolio_heat:.2%}")
    print(f"Heat Capacity: ${result.portfolio_heat_capacity:,.2f}")
    print(f"Correlation Capacity: ${result.correlation_risk_capacity:,.2f}")
    print(f"Permitted Risk Budget: ${result.permitted_risk_budget:,.2f}")
    print(f"Executable Floor Shares: {result.executable_position_size:.4f}")
    print(f"Actual Total Risk: ${result.actual_total_risk:,.2f}")
    print(f"Actual Total Risk <= Permitted: {result.actual_total_risk <= result.permitted_risk_budget}")


if __name__ == "__main__":
    main()
