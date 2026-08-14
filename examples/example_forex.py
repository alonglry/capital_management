"""
Example 2: Single Forex Pair Capital Allocation.
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
    print("      CAPITAL MANAGEMENT ENGINE — EXAMPLE 2: FOREX TRADE")
    print("=" * 70)

    # 1. Setup Account State ($100,000 equity, USD)
    account = AccountState(equity=100000.0, cash=75000.0, currency="USD")

    # 2. Proposed Forex Trade Candidate (Long EURUSD at 1.08500, stop at 1.08200 -> 30 pips)
    trade = TradeCandidate(
        symbol="EURUSD",
        asset_class="forex",
        side="long",
        entry_price=1.08500,
        proposed_stop_price=1.08200,
        pip_value_per_lot=10.0,  # $10 per pip for 1 standard lot
        strategy_id="breakout",
        spread=0.00015,  # 1.5 pips spread
        commission=5.0,  # $5 per lot round turn
        expected_slippage=0.00005,  # 0.5 pips slippage
    )

    # 3. Market Data (ATR ratio = 1.0)
    market_data = MarketData(
        atr={"EURUSD": 0.0060},
        reference_atr={"EURUSD": 0.0060},
    )

    # 4. Configuration
    config = CapitalManagementConfig(
        base_risk_pct=0.005,  # 0.5% base risk ($500)
        stress_policy="reduce",  # Reduce size if stress limit reached
        stress_limits={"max_stress_risk_pct": 0.025, "gap_pct": 0.003, "extra_slippage_pct": 0.001},
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
    print(f"Pair:                   {result.symbol} ({result.side.upper()})")
    print(f"Base Risk Budget:       ${result.base_risk_budget:,.2f}")
    print(f"Final Permitted Risk:   ${result.final_risk_budget:,.2f} ({result.final_risk_pct:.2%})")
    print(f"Entry / Stop Level:     {result.entry_price:.5f} / {result.stop_price:.5f}")
    print(f"Stop Distance (Pips):   {result.stop_distance / 0.0001:.1f} pips")
    print(f"Raw Position Size:      {result.raw_position_size:.4f} lots")
    print(f"Final Position Size:    {result.final_position_size:.2f} lots")
    print(f"Estimated Tx Cost:      ${result.transaction_cost:,.2f}")
    print(f"Stress Loss:            ${result.stress_loss:,.2f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
