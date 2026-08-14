"""
Capital Management Pipeline Executor.
"""

from typing import List, Optional

from capital_management.models.account import AccountState
from capital_management.models.config import CapitalManagementConfig
from capital_management.models.market_data import MarketData
from capital_management.models.portfolio import Position
from capital_management.models.result import CapitalManagementResult
from capital_management.models.state import CapitalManagementState
from capital_management.models.trade_candidate import TradeCandidate
from capital_management.modules.base_module import BaseRiskModule
from capital_management.modules.base_risk import BaseRiskModule as BaseRiskBudgetModule
from capital_management.modules.conviction_allocator import ConvictionRiskAllocatorModule
from capital_management.modules.correlation_risk import CorrelationRiskModule
from capital_management.modules.drawdown_governor import DrawdownGovernorModule
from capital_management.modules.factor_exposure import FactorExposureModule
from capital_management.modules.final_validation import FinalValidationModule
from capital_management.modules.portfolio_heat import PortfolioHeatModule
from capital_management.modules.position_sizing import PositionSizingModule
from capital_management.modules.stop_risk import StopRiskModule
from capital_management.modules.strategy_allocation import StrategyAllocationModule
from capital_management.modules.stress_test import StressTestModule
from capital_management.modules.transaction_cost import TransactionCostModule
from capital_management.modules.volatility_governor import VolatilityGovernorModule


def default_pipeline_modules() -> List[BaseRiskModule]:
    """
    Returns default standard sequence of 13 risk modules.
    """
    return [
        BaseRiskBudgetModule(),
        ConvictionRiskAllocatorModule(),
        DrawdownGovernorModule(),
        VolatilityGovernorModule(),
        StrategyAllocationModule(),
        PortfolioHeatModule(),
        CorrelationRiskModule(),
        FactorExposureModule(),
        StopRiskModule(),
        PositionSizingModule(),
        TransactionCostModule(),
        StressTestModule(),
        FinalValidationModule(),
    ]


class CapitalManagementPipeline:
    """
    Modular, pipeline-based execution engine for capital management.

    Executes a sequence of independent risk modules over a shared state object.
    Supports modular replacement, custom step ordering, toggled modules, and full auditability.
    """

    def __init__(self, modules: Optional[List[BaseRiskModule]] = None):
        """
        Initializes the pipeline with a sequence of risk modules.

        Args:
            modules (Optional[List[BaseRiskModule]]): List of risk module instances. If None, uses default 12-module pipeline.
        """
        self.modules: List[BaseRiskModule] = modules if modules is not None else default_pipeline_modules()

    def run(
        self,
        account: AccountState,
        portfolio: List[Position],
        trade: TradeCandidate,
        market_data: Optional[MarketData] = None,
        config: Optional[CapitalManagementConfig] = None,
    ) -> CapitalManagementResult:
        """
        Executes the capital management pipeline on the provided input state.

        Args:
            account (AccountState): Current account state.
            portfolio (List[Position]): Active open positions.
            trade (TradeCandidate): Proposed candidate trade.
            market_data (Optional[MarketData]): External market data container.
            config (Optional[CapitalManagementConfig]): Configuration parameters and module toggles.

        Returns:
            CapitalManagementResult: Structured result object containing decision, sizes, trace, and module summaries.
        """
        if market_data is None:
            market_data = MarketData()
        if config is None:
            config = CapitalManagementConfig()

        state = CapitalManagementState(
            account=account,
            portfolio=portfolio,
            trade=trade,
            market_data=market_data,
            config=config,
        )

        state.add_trace("Pipeline", f"Starting execution of {len(self.modules)} modules for {trade.symbol} ({trade.asset_class})")

        # Execute each module in sequence
        for module in self.modules:
            state = module.process(state)

        # Build final CapitalManagementResult
        result = CapitalManagementResult(
            approved=state.approved,
            symbol=trade.symbol,
            side=trade.side,
            asset_class=trade.asset_class,
            raw_position_size=state.raw_position_size,
            final_position_size=state.final_position_size,
            entry_price=trade.entry_price,
            stop_price=trade.proposed_stop_price,
            stop_distance=state.stop_distance,
            base_risk_budget=state.base_risk_budget,
            requested_risk_budget=state.requested_risk_budget,
            requested_risk_pct=state.requested_risk_pct,
            final_risk_budget=state.adjusted_risk_budget,
            final_risk_pct=state.final_risk_pct,
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
        )

        return result
