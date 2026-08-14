"""
Example 4: Multiple Equity Positions (Heat & Correlation Governance).
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
    print("  CAPITAL MANAGEMENT ENGINE — EXAMPLE 4: MULTI-EQUITY PORTFOLIO")
    print("=" * 70)

    # 1. Account state in drawdown (Peak = 100k, Current = 92k -> DD = 8%, Tier multiplier = 0.75)
    account = AccountState(equity=92000.0, cash=40000.0, currency="USD", peak_equity=100000.0)

    # 2. Existing Open Positions ($2,000 + $1,500 = $3,500 total risk -> 3.8% current heat)
    portfolio = [
        Position(
            symbol="MSFT",
            asset_class="equity",
            side="long",
            quantity=100,
            entry_price=300.0,
            current_price=310.0,
            stop_price=280.0,
            monetary_risk_at_stop=2000.0,
            strategy_id="trend",
            sector="Technology",
            beta=1.1,
        ),
        Position(
            symbol="NVDA",
            asset_class="equity",
            side="long",
            quantity=50,
            entry_price=400.0,
            current_price=420.0,
            stop_price=370.0,
            monetary_risk_at_stop=1500.0,
            strategy_id="breakout",
            sector="Technology",
            beta=1.5,
        ),
    ]

    # 3. Trade Candidate (AMD)
    trade = TradeCandidate(
        symbol="AMD",
        asset_class="equity",
        side="long",
        entry_price=110.0,
        proposed_stop_price=100.0,
        strategy_id="breakout",
        sector="Technology",
        beta=1.4,
    )

    # 4. Correlation Matrix
    corr_matrix = {
        "MSFT": {"MSFT": 1.0, "NVDA": 0.75, "AMD": 0.70},
        "NVDA": {"MSFT": 0.75, "NVDA": 1.0, "AMD": 0.80},
        "AMD": {"MSFT": 0.70, "NVDA": 0.80, "AMD": 1.0},
    }
    market_data = MarketData(correlation_matrix=corr_matrix)

    # 5. Configuration (Base risk = 0.5% -> $460, DD mult = 0.75 -> $345, Max heat = 5% -> $4,600 cap)
    config = CapitalManagementConfig(
        base_risk_pct=0.005,
        max_portfolio_heat_pct=0.05,
        max_correlation_adjusted_risk_pct=0.04,
        factor_limits={"Technology": 0.70, "market_beta": 1.5},
    )

    pipeline = CapitalManagementPipeline()
    result = pipeline.run(account=account, portfolio=portfolio, trade=trade, market_data=market_data, config=config)

    print("\n--- CALCULATION TRACE ---")
    for log in result.calculation_trace:
        print(log)

    print("\n--- DECISION RESULT ---")
    print(f"Approved:                   {result.approved}")
    print(f"Symbol:                     {result.symbol}")
    print(f"Current Portfolio Heat:     {result.current_portfolio_heat:.2%}")
    print(f"Projected Portfolio Heat:   {result.projected_portfolio_heat:.2%}")
    print(f"Corr-Adjusted Risk:         {result.correlation_adjusted_risk:.2%}")
    print(f"Permitted Risk Budget:      ${result.final_risk_budget:,.2f}")
    print(f"Final Position Size:        {result.final_position_size:,.0f} shares")
    print("=" * 70)


if __name__ == "__main__":
    main()
