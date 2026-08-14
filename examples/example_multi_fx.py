"""
Example 3: Multiple Correlated FX Trades & Factor Exposure Check.
"""

from capital_management.models import (
    AccountState,
    CapitalManagementConfig,
    MarketData,
    Position,
    TradeCandidate,
)
from capital_management.pipeline import CapitalManagementPipeline


def main():
    print("=" * 70)
    print("  CAPITAL MANAGEMENT ENGINE — EXAMPLE 3: MULTI-PAIR FX FACTOR RISKS")
    print("=" * 70)

    account = AccountState(equity=100000.0, cash=50000.0, currency="USD")

    # Open Positions: 1 lot EURUSD Long (USD = -1) + 1 lot GBPUSD Long (USD = -1) -> Total USD = -2
    portfolio = [
        Position(
            symbol="EURUSD",
            asset_class="forex",
            side="long",
            quantity=1.0,
            entry_price=1.0850,
            current_price=1.0870,
            stop_price=1.0820,
            monetary_risk_at_stop=300.0,
            strategy_id="fx_trend",
        ),
        Position(
            symbol="GBPUSD",
            asset_class="forex",
            side="long",
            quantity=1.0,
            entry_price=1.2700,
            current_price=1.2730,
            stop_price=1.2650,
            monetary_risk_at_stop=500.0,
            strategy_id="fx_trend",
        ),
    ]

    # Candidate Trade: 1 lot AUDUSD Long (would increase net USD exposure to -3)
    trade = TradeCandidate(
        symbol="AUDUSD",
        asset_class="forex",
        side="long",
        entry_price=0.6500,
        proposed_stop_price=0.6450,
        pip_value_per_lot=10.0,
        strategy_id="fx_trend",
    )

    # Config with USD factor limit = 2.0
    config = CapitalManagementConfig(
        factor_limits={"USD": 2.0, "EUR": 2.0, "GBP": 2.0, "AUD": 2.0},
    )

    pipeline = CapitalManagementPipeline()
    result = pipeline.run(account=account, portfolio=portfolio, trade=trade, market_data=MarketData(), config=config)

    print("\n--- CALCULATION TRACE ---")
    for log in result.calculation_trace:
        print(log)

    print("\n--- DECISION RESULT ---")
    print(f"Approved:               {result.approved}")
    print(f"Symbol:                 {result.symbol}")
    print(f"Projected Factors:      {result.factor_exposure}")
    print(f"Rejection Reasons:      {result.rejection_reasons}")
    print("=" * 70)


if __name__ == "__main__":
    main()
