# Modular Capital Management Engine for Equity and Forex Trading

A production-quality, modular, pipeline-based capital management engine for Equities and Forex trading.

It determines strategy conviction demand, maximum permissible risk budget, and final position size for a proposed trade candidate while enforcing strict portfolio-level risk limits, correlation constraints, factor exposures, transaction cost adjustments, and stress scenarios.

---

## 1. Overall Architecture

The engine uses a pipeline-based modular design. Every risk management step is an independent module with explicit input and output schemas, no hidden state, and complete auditability.

```text
Portfolio State + Trade Candidate + Configuration + Market Data (+ InstrumentSpec)
                                      ↓
                         CapitalManagementPipeline
                                      ↓
  [1] Base Risk Budget             (R0 = Equity × Base Risk %)
  [2] Conviction Risk Allocator    (R_requested = R0 × Conviction_Mult × Conflict_Mult)
  [3] Drawdown Governor           (R1 = R_prev × Drawdown Multiplier)
  [4] Volatility Governor         (R2 = R1 × Volatility Multiplier)
  [5] Strategy Allocation         (R3 = R2 × Strategy Multiplier)
  [6] Portfolio Heat Check        (Capacity check against max heat %)
  [7] Correlation Risk Check      (Correlation-adjusted stop-loss risk proxy matrix analysis)
  [8] Factor Exposure Check       (FX Currency breakdown & Equity Factors)
  [9] Stop-Loss Risk Calculation  (Stop distance & account currency conversion)
 [10] Position Sizing             (Shares/Lots with broker rules & iterative cost loop)
 [11] Transaction Cost Module     (Canonical cost calculation: spread, commission, slippage)
 [12] Stress Test                 (Stress loss capacity constraint & gap/slippage scenario)
 [13] Actual Risk Reconciliation  (Recalculates actual_total_risk = actual_stop + actual_cost)
 [14] Final Risk Validation       (Safety gate check across 17+ invariant criteria)
                                      ↓
                           CapitalManagementResult
```

---

## 2. Risk Budget Accounting Stages

- `base_risk_budget`: Initial unconstrained risk budget ($R_0 = \text{Equity} \times \text{BaseRisk\%}$).
- `requested_risk_budget`: Strategy conviction-scaled risk budget ($R_{\text{requested}}$).
- `governed_risk_budget`: Risk budget after soft governors (Drawdown, Volatility, Strategy Allocation).
- `permitted_risk_budget`: Hard constrained ceiling computed as:
  $$\text{permitted\_risk\_budget} = \min(\text{governed\_risk\_budget}, \text{trade\_capacity}, \text{heat\_capacity}, \text{correlation\_capacity}, \text{factor\_capacity}, \text{stress\_capacity})$$
- `actual_stop_loss_risk`: Pure monetary loss at stop loss level ($q \times \text{monetary\_risk\_per\_unit}$).
- `actual_transaction_cost`: Total execution costs ($C(q)$: spread, commission, slippage).
- `actual_total_risk`: Effective total risk ($= \text{actual\_stop\_loss\_risk} + \text{actual\_transaction\_cost} \le \text{permitted\_risk\_budget}$).

---

## 3. Instrument Metadata & Currency Conversion Layer

`InstrumentSpec` defines sizing increments, contract sizes, and valuations.
- `instrument_metadata_source`: Options `('explicit', 'broker', 'exchange', 'market_data', 'legacy_default')`. Production capital management rejects unverified `legacy_default` metadata.
- **Account Currency Conversion**: Automatically converts quote currency to account settlement currency:
  - Direct conversion if quote currency equals account currency.
  - Inversion ($1/\text{price}$) if base currency equals account currency.
  - Lookup via `market_data.fx_rates` (e.g. `GBPUSD` rate for a GBP quote instrument with USD account). Missing conversion rates trigger a hard rejection.

---

## 4. Position Sizing & Transaction Cost Iteration Loop

Position sizing converts `permitted_risk_budget` into executable units:
1. Validates broker rules (`min_quantity <= max_quantity`, `quantity_increment > 0`, increment alignment).
2. Computes floor-rounded theoretical quantity $q = \lfloor (\text{budget} / \text{risk\_per\_unit}) / \text{qty\_inc} \rfloor \times \text{qty\_inc}$.
3. Calls canonical `calculate_transaction_cost(state, q)` to compute exact costs $C(q)$.
4. Iteratively steps down $q$ by `quantity_increment` until:
   $$\text{stop\_loss\_risk}(q) + \text{transaction\_cost}(q) \le \text{permitted\_risk\_budget}$$
5. If $q < \text{min\_quantity}$, the trade is rejected.

---

## 5. Directory Structure

```text
capital_management/
├── models/
│   ├── account.py           # AccountState
│   ├── portfolio.py         # Position & PortfolioState
│   ├── trade_candidate.py   # TradeCandidate (with validate_stop_direction)
│   ├── market_data.py       # MarketData (with fx_rates)
│   ├── config.py            # CapitalManagementConfig & ConvictionRiskConfig
│   ├── instrument.py        # InstrumentSpec & FX conversion layer
│   ├── state.py             # CapitalManagementState & ModuleResult
│   └── result.py            # CapitalManagementResult & trace models
├── modules/
│   ├── base_module.py       # BaseRiskModule, RiskTransformer, RiskConstraint
│   ├── base_risk.py         # Module 1: Base Risk Budget
│   ├── conviction_allocator.py # Module 2: Dynamic Conviction Risk Allocator
│   ├── conviction_mapping.py   # ConvictionMapping, LinearConvictionMapping, PowerConvictionMapping
│   ├── drawdown_governor.py # Module 3: Drawdown Governor
│   ├── volatility_governor.py # Module 4: Volatility Governor
│   ├── strategy_allocation.py# Module 5: Strategy Allocation
│   ├── portfolio_heat.py    # Module 6: Portfolio Heat Constraint
│   ├── correlation_risk.py # Module 7: Correlation-Adjusted Risk Constraint
│   ├── factor_exposure.py  # Module 8: Factor Exposure Constraint
│   ├── stop_risk.py        # Module 9: Stop-Loss Risk Calculation
│   ├── position_sizing.py  # Module 10: Position Sizing & Cost Iteration Loop
│   ├── transaction_cost.py # Module 11: Transaction Cost Module (Canonical cost function)
│   ├── stress_test.py      # Module 12: Stress Test Capacity Constraint
│   ├── risk_reconciliation.py # Module 13: Actual Risk Reconciliation
│   └── final_validation.py # Module 14: Final Risk Validation Safety Gate
├── pipeline/
│   └── capital_management_pipeline.py # Core generic pipeline executor
├── merton_dynamic.py        # Deprecated legacy Merton functions
├── tests/
│   ├── test_base_risk.py ... test_conviction_allocator.py ... test_invariants.py
├── examples/
│   ├── example_equity.py
│   ├── example_forex.py
│   ├── example_multi_fx.py
│   └── example_multi_equity.py
└── README.md
```

---

## 6. Quick Start Usage

### Equity Trade Example with Conviction & Custom FX Rates

```python
from capital_management.models import AccountState, TradeCandidate, InstrumentSpec, MarketData, CapitalManagementConfig
from capital_management.pipeline import CapitalManagementPipeline

account = AccountState(equity=100000.0, cash=75000.0, currency="USD")
trade = TradeCandidate(
    symbol="AAPL",
    asset_class="equity",
    side="long",
    entry_price=150.0,
    proposed_stop_price=145.0,
    strategy_id="momentum",
    slope_long=1.30,
    threshold_long=1.00,
)
instrument = InstrumentSpec(
    symbol="AAPL",
    asset_class="EQUITY",
    contract_size=1.0,
    quantity_increment=1.0,
    min_quantity=1.0,
    max_quantity=10000.0,
    point_value=1.0,
    quote_currency="USD",
    instrument_metadata_source="explicit",
)

pipeline = CapitalManagementPipeline()
result = pipeline.run(account=account, portfolio=[], trade=trade, instrument=instrument)

print(f"Approved: {result.approved}")
print(f"Permitted Risk Budget: ${result.permitted_risk_budget:,.2f}")
print(f"Executable Size: {result.final_position_size} shares")
print(f"Actual Total Risk: ${result.actual_total_risk:,.2f}")
print(f"Binding Constraints: {result.binding_constraints}")
```

---

## 7. Running Unit Tests and Examples

Run all unit tests with `.venv_fx`:

```bash
.venv_fx/bin/pytest capital_management/tests
```

Run example scripts:

```bash
.venv_fx/bin/python -m capital_management.examples.example_equity
.venv_fx/bin/python -m capital_management.examples.example_forex
.venv_fx/bin/python -m capital_management.examples.example_multi_fx
.venv_fx/bin/python -m capital_management.examples.example_multi_equity
```
