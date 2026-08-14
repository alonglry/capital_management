# Modular Capital Management Engine for Equity and Forex Trading

A production-quality, modular, pipeline-based capital management engine for Equities and Forex trading.

It determines strategy conviction demand, maximum permissible risk budget, and final position size for a proposed trade candidate while enforcing strict portfolio-level risk limits, correlation constraints, factor exposures, transaction cost adjustments, and stress scenarios.

---

## 1. Overall Architecture

The engine uses a pipeline-based modular design. Every risk management step is an independent module with explicit input and output schemas, no hidden state, and complete auditability.

```text
Portfolio State + Trade Candidate + Configuration + Market Data
                              ↓
                CapitalManagementPipeline
                              ↓
  [1] Base Risk Budget             (R0 = Equity × Base Risk %)
  [2] Conviction Risk Allocator    (R_requested = R0 × Conviction_Mult × Conflict_Mult)
  [3] Drawdown Governor           (R1 = R_prev × Drawdown Multiplier)
  [4] Volatility Governor         (R2 = R1 × Volatility Multiplier)
  [5] Strategy Allocation         (R3 = R2 × Strategy Multiplier)
  [6] Portfolio Heat Check        (Capacity check against max heat %)
  [7] Correlation / Risk Check    (sqrt(r^T Σ r) matrix analysis)
  [8] Factor Exposure Check       (FX Currency breakdown & Equity Factors)
  [9] Stop-Loss Risk Calculation  (stop distance & pip / point conversion)
 [10] Position Sizing             (Equities shares & Forex lots/units)
 [11] Transaction Cost Adjustment (Spread, commission, slippage cost sizing)
 [12] Stress Test                 (Gap & extreme execution stress loss limits)
 [13] Final Risk Validation       (Gate check across all 8 criteria)
                              ↓
                   CapitalManagementResult
```

---

## 2. Dynamic Conviction Risk Allocator (`ConvictionRiskAllocatorModule`)

The `ConvictionRiskAllocatorModule` converts strategy conviction (long & short slopes/thresholds) into a **requested monetary risk budget**.

### Conviction Formulas

1. **Side Convictions**:
   $$\text{max\_conviction}_{\text{side}} = \text{threshold}_{\text{side}} \times \text{conviction\_threshold\_multiplier}$$
   $$\text{raw}_{\text{side}} = \frac{\text{slope}_{\text{side}} - \text{threshold}_{\text{side}}}{\text{max\_conviction}_{\text{side}} - \text{threshold}_{\text{side}}}$$
   $$\text{conviction}_{\text{side}} = \text{clip}(\text{raw}_{\text{side}}, 0.0, 1.0)$$

2. **Net Conviction & Signal Conflict**:
   $$\text{net\_conviction} = \text{long\_conviction} - \text{short\_conviction}$$
   $$\text{directional\_strength} = |\text{net\_conviction}|$$
   $$\text{signal\_conflict} = \min(\text{long\_conviction}, \text{short\_conviction})$$

3. **Conflict Penalty & Conviction Mapping**:
   $$\text{conflict\_multiplier} = 1 - \text{conflict\_penalty} \times \text{signal\_conflict}$$
   $$\text{conviction\_multiplier} = \text{min\_mult} + (\text{max\_mult} - \text{min\_mult}) \times \text{mapping}(\text{directional\_strength})$$
   $$\text{R}_{\text{requested}} = \text{R}_{\text{base}} \times \text{conviction\_multiplier} \times \text{conflict\_multiplier}$$

Supported mapping implementations (`ConvictionMapping`):
- `LinearConvictionMapping`: $\text{mapping}(x) = x$
- `PowerConvictionMapping`: $\text{mapping}(x) = x^{\gamma}$ ($\gamma$ configurable)

---

## 3. Directory Structure

```text
capital_management/
├── models/
│   ├── account.py           # AccountState
│   ├── portfolio.py         # Position & PortfolioState
│   ├── trade_candidate.py   # TradeCandidate
│   ├── market_data.py       # MarketData
│   ├── config.py            # CapitalManagementConfig & ConvictionRiskConfig
│   ├── state.py             # CapitalManagementState & ModuleResult
│   └── result.py            # CapitalManagementResult & trace models
├── modules/
│   ├── base_module.py       # BaseRiskModule Abstract Base Class
│   ├── base_risk.py         # Module 1: Base Risk Budget
│   ├── conviction_allocator.py # Module 2: Conviction Risk Allocator
│   ├── conviction_mapping.py   # ConvictionMapping, LinearConvictionMapping, PowerConvictionMapping
│   ├── drawdown_governor.py # Module 3: Drawdown Governor
│   ├── volatility_governor.py # Module 4: Volatility Governor
│   ├── strategy_allocation.py# Module 5: Strategy Allocation
│   ├── portfolio_heat.py    # Module 6: Portfolio Heat
│   ├── correlation_risk.py # Module 7: Correlation-Adjusted Portfolio Risk
│   ├── factor_exposure.py  # Module 8: Factor Exposure
│   ├── stop_risk.py        # Module 9: Stop-Loss Risk Calculation
│   ├── position_sizing.py  # Module 10: Position Sizing
│   ├── transaction_cost.py # Module 11: Transaction Cost Adjustment
│   ├── stress_test.py      # Module 12: Stress Test
│   └── final_validation.py # Module 13: Final Risk Validation
├── pipeline/
│   └── capital_management_pipeline.py # Core generic pipeline executor
├── merton_dynamic.py        # Deprecated legacy Merton functions with compatibility wrapper
├── tests/
│   ├── test_base_risk.py ... test_conviction_allocator.py ... test_pipeline.py
├── examples/
│   ├── example_equity.py
│   ├── example_forex.py
│   ├── example_multi_fx.py
│   └── example_multi_equity.py
└── README.md
```

---

## 4. Quick Start Usage

### Equity Trade Example with Conviction

```python
from capital_management.models import AccountState, TradeCandidate, CapitalManagementConfig
from capital_management.pipeline import CapitalManagementPipeline

account = AccountState(equity=100000.0, cash=75000.0)
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
)

pipeline = CapitalManagementPipeline()
result = pipeline.run(account=account, portfolio=[], trade=trade)

print(f"Approved: {result.approved}")
print(f"Base Risk Budget: ${result.base_risk_budget:,.2f}")
print(f"Requested Risk Budget: ${result.requested_risk_budget:,.2f}")
print(f"Final Permitted Risk: ${result.final_risk_budget:,.2f}")
print(f"Final Position Size: {result.final_position_size} shares")
```

---

## 5. Enabling / Disabling Modules

Modules can be enabled or disabled via `CapitalManagementConfig.modules`:

```python
config = CapitalManagementConfig(
    modules={
        "base_risk": True,
        "conviction_allocator": True,
        "drawdown_governor": True,
        "volatility_governor": False,
        "strategy_allocation": True,
        "portfolio_heat": True,
        "correlation_check": True,
        "factor_check": True,
        "stop_risk": True,
        "position_sizing": True,
        "transaction_cost": True,
        "stress_test": True,
        "final_validation": True,
    }
)
```

---

## 6. Running Unit Tests and Examples

Run all unit tests:

```bash
.venv_fx/bin/python -m unittest discover -s capital_management/tests
```

Run example scripts:

```bash
.venv_fx/bin/python -m capital_management.examples.example_equity
.venv_fx/bin/python -m capital_management.examples.example_forex
.venv_fx/bin/python -m capital_management.examples.example_multi_fx
.venv_fx/bin/python -m capital_management.examples.example_multi_equity
```
