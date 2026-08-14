"""
Capital Management Pipeline Executor.
"""

from typing import List, Optional

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.instrument import InstrumentSpec
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.result import CapitalManagementResult
from capital_management.models.state import CapitalManagementState, ModuleResult
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.base_risk import BaseRiskBudgetModule
from capital_management.modules.conviction_allocator import ConvictionRiskAllocatorModule
from capital_management.modules.correlation_risk import CorrelationRiskModule
from capital_management.modules.drawdown_governor import DrawdownGovernorModule
from capital_management.modules.factor_exposure import FactorExposureModule
from capital_management.modules.final_validation import FinalValidationModule
from capital_management.modules.portfolio_heat import PortfolioHeatModule
from capital_management.modules.position_sizing import PositionSizingModule
from capital_management.modules.risk_reconciliation import ActualRiskReconciliationModule
from capital_management.modules.stop_risk import StopRiskModule
from capital_management.modules.strategy_allocation import StrategyAllocationModule
from capital_management.modules.stress_test import StressTestModule
from capital_management.modules.transaction_cost import TransactionCostModule
from capital_management.modules.volatility_governor import VolatilityGovernorModule


def default_pipeline_modules() -> List[BaseRiskModule]:
    """
    Returns default standard sequence of 14 risk modules.
    Ensures pre-sizing constraints (PortfolioHeat, Correlation, Factor, Stress) run BEFORE PositionSizing.
    """
    return [
        BaseRiskBudgetModule(),
        ConvictionRiskAllocatorModule(),
        DrawdownGovernorModule(),
        VolatilityGovernorModule(),
        StrategyAllocationModule(),
        StopRiskModule(),
        PortfolioHeatModule(),
        CorrelationRiskModule(),
        FactorExposureModule(),
        StressTestModule(),
        PositionSizingModule(),
        TransactionCostModule(),
        ActualRiskReconciliationModule(),
        FinalValidationModule(),
    ]


class CapitalManagementPipeline:
    """
    Modular, pipeline-based execution engine for capital management.

    Executes a sequence of independent risk modules over a shared state object.
    Supports modular replacement, custom step ordering, toggled modules, early termination, and full auditability.
    """

    def __init__(self, modules: Optional[List[BaseRiskModule]] = None):
        """
        Initializes pipeline with a sequence of risk modules.

        Args:
            modules (Optional[List[BaseRiskModule]]): List of risk module instances. If None, uses default 14-module pipeline.
        """
        self.modules: List[BaseRiskModule] = modules if modules is not None else default_pipeline_modules()
        self.validate_module_dependencies()

    def validate_module_dependencies(self) -> None:
        """
        Validates module order dependencies for custom module sequences.
        """
        names = [m.name for m in self.modules]

        if "position_sizing" in names:
            idx_sizing = names.index("position_sizing")
            if "stop_risk" in names and names.index("stop_risk") > idx_sizing:
                raise ValueError("Dependency Error: Module 'position_sizing' cannot execute before 'stop_risk'")
            if "stress_test" in names and names.index("stress_test") > idx_sizing:
                raise ValueError("Dependency Error: Pre-sizing constraint 'stress_test' should execute before 'position_sizing'")
        if "transaction_cost" in names and "position_sizing" in names:
            if names.index("transaction_cost") < names.index("position_sizing"):
                raise ValueError("Dependency Error: Module 'transaction_cost' cannot execute before 'position_sizing'")
        if "risk_reconciliation" in names and "position_sizing" in names:
            if names.index("risk_reconciliation") < names.index("position_sizing"):
                raise ValueError("Dependency Error: Module 'risk_reconciliation' cannot execute before 'position_sizing'")

    def run(
        self,
        account: AccountState,
        portfolio: List[Position],
        trade: TradeCandidate,
        market_data: Optional[MarketData] = None,
        config: Optional[CapitalManagementConfig] = None,
        instrument: Optional[InstrumentSpec] = None,
    ) -> CapitalManagementResult:
        """
        Executes the capital management pipeline on the provided input state.
        """
        if market_data is None:
            market_data = MarketData()
        if config is None:
            config = CapitalManagementConfig()
        if instrument is None:
            instrument = InstrumentSpec.create_default(trade.symbol, trade.asset_class)

        state = CapitalManagementState(
            account=account,
            portfolio=portfolio,
            trade=trade,
            market_data=market_data,
            config=config,
            instrument=instrument,
        )

        state.add_trace("Pipeline", f"Starting execution of {len(self.modules)} modules for {trade.symbol} ({trade.asset_class})")

        has_upstream_rejection = False

        # Execute each module in sequence
        for module in self.modules:
            enabled = config.is_module_enabled(module.name)

            if not enabled:
                state.add_trace(module.name, "Module disabled in config. Status = SKIPPED")
                state.module_results[module.name] = ModuleResult(
                    module_name=module.name,
                    enabled=False,
                    input_summary={},
                    output_summary={},
                    status="SKIPPED",
                    reason="Module disabled in configuration.",
                )
                continue

            # Early Termination Semantics: If upstream rejection occurred, skip sizing/execution modules
            if has_upstream_rejection and module.module_type in ("sizing", "execution", "reconciliation"):
                state.add_trace(module.name, f"Skipping {module.name} due to upstream hard rejection.")
                state.module_results[module.name] = ModuleResult(
                    module_name=module.name,
                    enabled=True,
                    input_summary={},
                    output_summary={},
                    status="SKIPPED",
                    reason="Skipped downstream execution due to upstream module rejection.",
                )
                continue

            state = module.process(state)

            mod_res = state.module_results.get(module.name)
            if mod_res and mod_res.status in ("REJECT", "FAIL"):
                has_upstream_rejection = True

        # Build final CapitalManagementResult
        result = CapitalManagementResult(
            approved=state.approved,
            symbol=trade.symbol,
            side=trade.side,
            asset_class=trade.asset_class,
            base_risk_budget=state.base_risk_budget,
            requested_risk_budget=state.requested_risk_budget,
            requested_risk_pct=state.requested_risk_pct,
            governed_risk_budget=state.governed_risk_budget,
            trade_risk_capacity=state.trade_risk_capacity,
            portfolio_heat_capacity=state.portfolio_heat_capacity,
            correlation_risk_capacity=state.correlation_risk_capacity,
            factor_risk_capacity=state.factor_risk_capacity,
            stress_risk_capacity=state.stress_risk_capacity,
            permitted_risk_budget=state.permitted_risk_budget,
            raw_position_size=state.raw_position_size,
            executable_position_size=state.executable_position_size,
            final_position_size=state.final_position_size,
            entry_price=trade.entry_price,
            stop_price=trade.proposed_stop_price,
            stop_distance=state.stop_distance,
            actual_stop_loss_risk=state.actual_stop_loss_risk,
            actual_transaction_cost=state.actual_transaction_cost,
            actual_total_risk=state.actual_total_risk,
            final_risk_budget=state.permitted_risk_budget,
            final_risk_pct=state.actual_total_risk / account.equity if account.equity > 0 else 0.0,
            current_portfolio_heat=state.current_portfolio_heat,
            projected_portfolio_heat=state.projected_portfolio_heat,
            correlation_adjusted_risk=state.correlation_adjusted_risk,
            factor_exposure=state.factor_exposure,
            transaction_cost=state.total_transaction_cost,
            stress_loss=state.stress_loss,
            rejection_reasons=list(state.rejection_reasons),
            warnings=list(state.warnings),
            module_results=dict(state.module_results),
            calculation_trace=list(state.trace_logs),
            binding_constraints=list(state.binding_constraints),
        )

        return result
