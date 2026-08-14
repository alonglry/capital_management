"""
Example 1: Single Equity Trade Capital Allocation.
"""

from capital_management.models import (
    AccountState,
    CapitalManagementConfig,
    MarketData,
    TradeCandidate,
)
from capital_management.pipeline import CapitalManagementPipeline


def main():
    print("=" * 70)
    print("      CAPITAL MANAGEMENT ENGINE — EXAMPLE 1: EQUITY TRADE")
    print("=" * 70)

    # 1. Setup Account State ($100,000 equity, $75,000 cash)
    account = AccountState(equity=100000.0, cash=75000.0, currency="USD", peak_equity=100000.0)

    # 2. Proposed Trade Candidate (Long AAPL at $150.00, stop at $145.00)
    trade = TradeCandidate(
        symbol="AAPL",
        asset_class="equity",
        side="long",
        entry_price=150.0,
        proposed_stop_price=145.0,
        strategy_id="momentum",
        slope_long=1.30,
        threshold_long=1.00,
        slope_short=0.20,
        threshold_short=1.00,
        sector="Technology",
        country="US",
        beta=1.2,
        commission=0.005,  # $0.005 per share
        spread=0.02,  # $0.02 spread
        expected_slippage=0.001,  # 0.1% slippage
    )

    # 3. Market Data (Reference ATR = 3.0, Current ATR = 3.3 -> ATR ratio = 1.1)
    market_data = MarketData(
        atr={"AAPL": 3.3},
        reference_atr={"AAPL": 3.0},
    )

    # 4. Configuration
    config = CapitalManagementConfig(
        base_risk_pct=0.005,  # 0.5% base risk ($500)
        max_trade_risk_pct=0.0075,  # 0.75% max risk per trade
        max_portfolio_heat_pct=0.05,  # 5% max heat
    )

    # 5. Run Pipeline
    pipeline = CapitalManagementPipeline()
    result = pipeline.run(account=account, portfolio=[], trade=trade, market_data=market_data, config=config)

    # 6. Display Output Trace
    print("\n--- CALCULATION TRACE ---")
    for log in result.calculation_trace:
        print(log)

    print("\n--- DECISION RESULT ---")
    print(f"Approved:               {result.approved}")
    print(f"Symbol:                 {result.symbol} ({result.side.upper()})")
    print(f"Base Risk Budget:       ${result.base_risk_budget:,.2f}")
    print(f"Requested Risk Budget:  ${result.requested_risk_budget:,.2f} ({result.requested_risk_pct:.2%})")
    print(f"Final Permitted Risk:   ${result.final_risk_budget:,.2f} ({result.final_risk_pct:.2%})")
    print(f"Entry / Stop Price:     ${result.entry_price:.2f} / ${result.stop_price:.2f}")
    print(f"Stop Distance:          ${result.stop_distance:.2f}")
    print(f"Raw Position Size:      {result.raw_position_size:,.2f} shares")
    print(f"Final Position Size:    {result.final_position_size:,.0f} shares")
    print(f"Estimated Tx Cost:      ${result.transaction_cost:,.2f}")
    print(f"Stress Loss:            ${result.stress_loss:,.2f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
