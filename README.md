# Modular Capital Management Engine for Equity and Forex Trading

A production-grade, modular, pipeline-based capital management engine for Equities and Forex trading.

It determines strategy conviction demand, maximum permissible risk budget, and final position size for a proposed trade candidate while enforcing strict portfolio-level risk limits, correlation constraints, factor exposures, transaction cost adjustments, and stress scenarios.

---

## 1. Overall Architecture

The engine uses a pipeline-based modular design. Every risk management step is an independent module with explicit input and output schemas, no hidden state, and complete auditability.

```text
Portfolio State + Trade Candidate + Configuration + Market Data + Explicit InstrumentSpec
                                      ↓
                         CapitalManagementPipeline
                                      ↓
  [1] Base Risk Budget             (R0 = Equity Snapshot × Base Risk %)
  [2] Conviction Risk Allocator    (R_requested = R0 × Conviction_Mult × Conflict_Mult)
  [3] Drawdown Governor           (R1 = R_prev × Drawdown Multiplier)
  [4] Volatility Governor         (R2 = R1 × Volatility Multiplier)
  [5] Strategy Allocation         (R3 = R2 × Strategy Multiplier)
  [6] Stop-Loss Risk Calculation  (Stop distance & monetary_risk_per_unit)
  [7] Portfolio Heat Check        (Pre-sizing heat risk capacity)
  [8] Correlation Risk Check      (Pre-sizing correlation risk capacity)
  [9] Factor Exposure Check       (Pre-sizing factor risk capacity)
 [10] Stress Test                 (Pre-sizing stress loss capacity solver)
 [11] Position Sizing             (Integer-step quantity solver using solve_max_executable_quantity)
 [12] Transaction Cost Module     (Calculates actual_transaction_cost, short_borrow_cost, financing_cost)
 [13] Actual Risk Reconciliation  (Recalculates ledger & recomputes post-sizing heat/correlation/factor/stress)
 [14] Final Risk Validation       (Safety gate check across RiskLedger, RiskCapacityLedger & finite values)
                                      ↓
                           CapitalManagementResult
```

---

## 2. Risk Budget Accounting & Ledgers

The engine uses explicit risk budgets and formal ledgers:
- **`RiskLedger`**: Tracks `stop_loss_risk`, `transaction_cost`, `financing_cost`, `short_borrow_cost`, `normal_total_risk`, `incremental_gap_loss`, `incremental_stress_slippage_loss`, and `stress_total_risk`.
- **`RiskCapacityLedger`**: Tracks `trade_capacity`, `portfolio_heat_capacity`, `correlation_capacity`, `factor_capacity`, `stress_capacity`, and `permitted_capacity`.
- **`attempted_position_size` & `attempted_risk_ledger`**: Preserves measured diagnostic risk and attempted size when a trade is rejected, setting `final_position_size = 0.0` for safety.

---

## 3. Instrument Metadata & Verification

`InstrumentSpec` defines sizing increments, contract sizes, and valuations with strict verification:
- **Explicit Metadata Verification**: Requires `metadata_verified == True` and non-empty `metadata_source` in production mode.
- **Explicit Validation (`validate_for_capital_management`)**: Validates required fields for Equity vs. Forex before sizing.
- **Canonical Notional Calculation**: `calculate_notional_value(state, quantity)` calculates exact position notional value in account currency.

---

## 4. Single Canonical Quantity Solver

Position sizing and reconciliation use the single canonical solver `solve_max_executable_quantity`:
1. Converts quantity bounds into integer step indices $N_{\text{min}}$ and $N_{\text{max}}$ using `quantity_to_step_index(q, qty_inc)`.
2. Solves for maximum executable quantity $q = N \times \text{qty\_inc}$ satisfying $\text{stop\_risk}(q) + \text{transaction\_cost}(q) \le \text{permitted\_budget}$.
3. Eliminates floating-point accumulation errors during step-down iteration, natively supporting non-decimal steps (`0.25`, `0.05`, `0.125`, `2.5`).

---

## 5. Directory Structure

```text
capital_management/
├── models/
│   ├── account.py           # AccountState
│   ├── portfolio.py         # Position & PortfolioState
│   ├── trade_candidate.py   # TradeCandidate (with validate_stop_direction)
│   ├── market_data.py       # MarketData (with fx_rates & as_of_timestamp)
│   ├── config.py            # CapitalManagementConfig & ConvictionRiskConfig
│   ├── instrument.py        # InstrumentSpec & FX conversion layer
│   ├── ledger.py            # RiskLedger & RiskCapacityLedger
│   ├── state.py             # CapitalManagementState & ModuleResult
│   └── result.py            # CapitalManagementResult & trace models
├── modules/
│   ├── base_module.py       # BaseRiskModule, RiskTransformer, RiskConstraint
│   ├── base_risk.py         # Module 1: Base Risk Budget
│   ├── conviction_allocator.py # Module 2: Dynamic Conviction Risk Allocator
│   ├── drawdown_governor.py # Module 3: Drawdown Governor
│   ├── volatility_governor.py # Module 4: Volatility Governor
│   ├── strategy_allocation.py# Module 5: Strategy Allocation
│   ├── stop_risk.py        # Module 6: Stop-Loss Risk Calculation
│   ├── portfolio_heat.py    # Module 7: Portfolio Heat Constraint
│   ├── correlation_risk.py # Module 8: Correlation-Adjusted Risk Constraint
│   ├── factor_exposure.py  # Module 9: Factor Exposure Constraint
│   ├── stress_test.py      # Module 10: Stress Test Capacity Constraint
│   ├── quantity_solver.py  # Integer step utility & solve_max_executable_quantity solver
│   ├── position_sizing.py  # Module 11: Position Sizing
│   ├── transaction_cost.py # Module 12: Transaction Cost Module
│   ├── risk_reconciliation.py # Module 13: Actual Risk Reconciliation
│   └── final_validation.py # Module 14: Final Risk Validation Safety Gate
├── pipeline/
│   └── capital_management_pipeline.py # Pipeline executor with hash & timestamp checks
├── tests/
│   └── test_*.py            # Comprehensive unit and invariant test suite (71 tests)
├── examples/
│   ├── example_equity.py
│   ├── example_forex.py
│   ├── example_multi_fx.py
│   └── example_multi_equity.py
└── README.md
```

---

## 6. Quick Start Usage

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
    metadata_verified=True,
    metadata_source="explicit",
)

pipeline = CapitalManagementPipeline()
result = pipeline.run(account=account, portfolio=[], trade=trade, instrument=instrument)

print(f"Approved: {result.approved}")
print(f"Permitted Risk Budget: ${result.permitted_risk_budget:,.2f}")
print(f"Executable Size: {result.final_position_size} shares")
print(f"Actual Total Risk: ${result.actual_total_risk:,.2f}")
print(f"Calculation Hash: {result.calculation_input_hash[:8]}")
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
