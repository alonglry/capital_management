"""
Worked Example — Forex Trade Sizing with Refactored Capital Management Engine.
"""

from capital_management.models import (
    AccountState,
    CapitalManagementConfig,
    ConvictionRiskConfig,
    InstrumentSpec,
    MarketData,
    TradeCandidate,
)
from capital_management.pipeline import CapitalManagementPipeline


def main():
    account = AccountState(equity=50000.0, cash=50000.0, currency="USD")
    trade = TradeCandidate(
        symbol="EURUSD",
        asset_class="forex",
        side="long",
        entry_price=1.0850,
        proposed_stop_price=1.0810,  # 40 pips stop distance
        pip_value_per_lot=10.0,
        spread=0.0001,  # 1 pip spread
        commission=3.50,
        slope_long=3.0,
        threshold_long=1.0,
        slope_short=0.0,
        threshold_short=1.0,
        strategy_id="fx_trend",
    )
    instrument = InstrumentSpec.create_default("EURUSD", "forex")

    config = CapitalManagementConfig(
        base_risk_pct=0.01,
        stress_policy="reduce",
        conviction_risk=ConvictionRiskConfig(
            min_multiplier=0.5,
            max_multiplier=1.5,
        ),
    )

    pipeline = CapitalManagementPipeline()
    result = pipeline.run(
        account=account,
        portfolio=[],
        trade=trade,
        market_data=MarketData(),
        config=config,
        instrument=instrument,
    )

    print("=== FOREX TRADE CAPITAL MANAGEMENT REPORT ===")
    print(f"Symbol: {result.symbol} ({result.asset_class.upper()}) | Side: {result.side.upper()}")
    print(f"Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
    print(f"Base Risk Budget: ${result.base_risk_budget:,.2f}")
    print(f"Requested Conviction Risk: ${result.requested_risk_budget:,.2f} ({result.requested_risk_pct:.2%})")
    print(f"Governed Risk Budget: ${result.governed_risk_budget:,.2f}")
    print(f"Permitted Risk Budget: ${result.permitted_risk_budget:,.2f}")
    print(f"Theoretical Raw Lots: {result.raw_position_size:.4f}")
    print(f"Executable Floor Lots: {result.executable_position_size:.4f}")
    print(f"Actual Stop Loss Risk: ${result.actual_stop_loss_risk:,.2f}")
    print(f"Actual Transaction Cost: ${result.actual_transaction_cost:,.2f}")
    print(f"Actual Total Risk: ${result.actual_total_risk:,.2f}")
    print(f"Actual Total Risk <= Permitted: {result.actual_total_risk <= result.permitted_risk_budget}")


if __name__ == "__main__":
    main()
